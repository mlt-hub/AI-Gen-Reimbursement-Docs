"""生成 FPA工作量评估.xlsx"""

import json as _json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import hashlib
from difflib import SequenceMatcher
from copy import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font, Border
from openpyxl.styles import PatternFill

from ai_gen_reimbursement_docs.constants import (
    FPA_COL_SEQ, FPA_COL_SUBSYSTEM, FPA_COL_ASSET, FPA_COL_FUNC_POINT,
    FPA_COL_TYPE, FPA_COL_CLASSIFICATION, FPA_COL_EXPLANATION, FPA_COL_STATUS,
    FPA_COL_FORMULA_BASE, FPA_COL_ADJUST, FPA_COL_ELEMENTS, FPA_COL_FORMULA_WORKLOAD,
    FPA_TOTAL_COLS, FPA_COL_KEY_MAP,
)
from ai_gen_reimbursement_docs.excel_source import (
    replace_placeholders, strip_ai_marker, parse_module_tree_md,
    read_base_data_from_excel, safe_load_workbook,
)
from ai_gen_reimbursement_docs.fpa_profiles import (
    CUSTOM_RULES_PROFILE,
    CustomRulesProfile,
    FpaRuleSetConfig,
    adjust_value_for_type as _adjust_value_for_type,
    calculate_fpa_adjustment_for_row,
    current_fpa_rule_set_config,
    get_fpa_profile,
    group_tag as _group_tag,
    module_change_status as _module_change_status,
    reset_current_fpa_rule_set_config,
    resolve_fpa_execution_config,
    set_current_fpa_rule_set_config,
)
from ai_gen_reimbursement_docs.fpa_validator import (
    FpaValidationIssue,
    retryable_validation_issues,
    validate_fpa_rows,
    validation_feedback,
)
from ai_gen_reimbursement_docs.md_table import parse_md_table_row

logger = logging.getLogger('ai_gen_reimbursement_docs.gen_fpa')

VALID_FPA_TYPES = {"EI", "ILF", "EQ", "EO", "EIF"}
FPA_PROFILE = CUSTOM_RULES_PROFILE
RULE_HITS_KEY = "_规则命中详情"
CONFIG_WARNING_PREFIX = "FPA 配置 warning:"
EXPLANATION_REQUIRED_LABELS = ("来源场景：", "业务数据：", "业务规则：", "计算说明：")
EXPLANATION_MISSING_HINTS = ("未识别到", "未明确说明", "需求未明确说明")
FPA_PROJECT_DESCRIPTION_MAX_CHARS = 5000
EXPLANATION_TABLE_COUNT_HINTS = ("按后台数据库变更的表个数计量", "按数据库表个数计量", "按表个数计量")


@dataclass(frozen=True)
class FpaPromptContext:
    """Rendered FPA prompts plus user-safe source labels."""

    system_prompt: str
    user_prompt: str
    core_rules: str
    core_rules_source: str
    system_prompt_source: str
    user_prompt_source: str


@dataclass
class FpaAuditReport:
    """FPA 预览/审核的结构化信息。"""

    profile: str
    profile_version: str
    strategy: str
    rule_set: str
    module: dict[str, object]
    process_total: int
    covered_processes: list[str]
    missing_processes: list[str]
    generation_counts: dict[str, int]
    warnings: list[str] = field(default_factory=list)
    raw_source: str = ""
    raw_rows: list[object] = field(default_factory=list)
    raw_warnings: list[str] = field(default_factory=list)
    rule_hits: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "profile_version": self.profile_version,
            "strategy": self.strategy,
            "rule_set": self.rule_set,
            "module": self.module,
            "coverage": {
                "process_total": self.process_total,
                "covered_count": len(self.covered_processes),
                "missing_count": len(self.missing_processes),
                "covered_processes": self.covered_processes,
                "missing_processes": self.missing_processes,
            },
            "generation_counts": self.generation_counts,
            "warnings": self.warnings,
            "raw_ai": {
                "source": self.raw_source,
                "warnings": self.raw_warnings,
                "raw_rows": self.raw_rows,
            },
            "rule_hits": self.rule_hits,
        }


def parse_meta_md(meta_md_path: str) -> dict[str, str]:
    """解析文档元数据.md 为扁平字典。支持跨多行的表格值。"""
    from ai_gen_reimbursement_docs.gen_spec import parse_meta_md
    return parse_meta_md(meta_md_path)


def _explanation_quality_warnings(
    *,
    group: dict[str, object],
    name: str,
    fpa_type: str,
    explanation: str,
) -> list[str]:
    """Check formal FPA calculation explanation quality without changing output."""
    text = str(explanation or "").strip()
    if not text:
        return []

    warnings: list[str] = []
    missing_labels = [label.rstrip("：") for label in EXPLANATION_REQUIRED_LABELS if label not in text]
    if missing_labels:
        warnings.append(
            f"{name} 计算依据说明格式不完整，缺少结构化项: {'、'.join(missing_labels)}"
        )

    source_prefix = (
        f"【{group.get('client_type', '')}】"
        f"{group.get('l1', '')}-{group.get('l2', '')}-{group.get('l3', '')}-"
    )
    if source_prefix.strip("-") and source_prefix not in text:
        expected_tail = "<数据组名称>" if fpa_type in {"ILF", "EIF"} else "<功能点名称>"
        warnings.append(
            f"{name} 计算依据说明来源场景未使用完整路径格式: {source_prefix}{expected_tail}"
        )

    if fpa_type and fpa_type not in text:
        warnings.append(f"{name} 计算依据说明的计算说明未明确当前 FPA 类型: {fpa_type}")

    if any(hint in text for hint in EXPLANATION_MISSING_HINTS):
        warnings.append(f"{name} 正式计算依据说明包含缺失提示，应移入 check/debug 输出")

    if any(hint in text for hint in EXPLANATION_TABLE_COUNT_HINTS):
        warnings.append(
            f"{name} 计算依据说明疑似将数据库表个数作为详细计量解释，应保留在计算依据归类而非计算依据说明"
        )

    return warnings


def _receiver_from_client_type(client_type: str, rules_text: str) -> str:
    """根据客户端类型判定接收者。"""
    default = "操作员"
    if not rules_text:
        logger.warning(
            "Excel 模板未配置「功能用户-接收者判定」，接收者将使用默认值，请在模板 Sheet 6 中补充"
        )
        return default

    for line in rules_text.split('\n'):
        line = line.strip()
        if '：' in line:
            keyword, receiver = line.split('：', 1)
            if keyword in client_type:
                return receiver.strip()
    return default


def _group_rows_by_l3(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """按客户端/一二三级模块聚合功能过程，供 FPA 三级模块规划使用。"""
    groups: list[dict[str, object]] = []
    index: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for r in rows:
        key = (
            str(r.get("客户端类型", "")).strip(),
            str(r.get("一级模块", "")).strip(),
            str(r.get("二级模块", "")).strip(),
            str(r.get("三级模块", "")).strip(),
        )
        group = index.get(key)
        if group is None:
            group = {
                "client_type": key[0],
                "l1": key[1],
                "l2": key[2],
                "l3": key[3],
                "l3_desc": str(r.get("三级模块整体功能描述", "") or "").strip(),
                "processes": [],
            }
            index[key] = group
            groups.append(group)
        elif not group.get("l3_desc") and r.get("三级模块整体功能描述"):
            group["l3_desc"] = str(r.get("三级模块整体功能描述", "")).strip()
        processes = group["processes"]
        if isinstance(processes, list):
            process_id = f"m{groups.index(group) + 1}_p{len(processes) + 1}"
            process_name = str(r.get("功能过程", "") or "").strip()
            process_desc = str(r.get("功能过程描述", "") or "").strip()
            processes.append({
                "process_id": process_id,
                "process_name": process_name,
                "description": process_desc,
                "name": process_name,
                "type": str(r.get("功能过程类型", "") or "").strip(),
                "desc": process_desc,
            })
    return groups


def _call_llm(
    prompt: str,
    system_prompt: str,
    api_key: str,
    model: str,
    base_url: str,
    tag: str = "",
    return_thinking: bool = False,
) -> str | tuple[str, str]:
    """调用 LLM（委托至 llm_client 公共模块）。"""
    from ai_gen_reimbursement_docs.llm_client import call_llm

    try:
        return call_llm(
            prompt=prompt, system=system_prompt,
            api_key=api_key, model=model, base_url=base_url, tag=tag,
            return_thinking=return_thinking,
        )
    except Exception as e:
        logger.warning("LLM 调用失败 [%s]: %s", tag, e)
        if return_thinking:
            return "", ""
        return ""


def _build_fpa_rule_rows(
    rows: list[dict[str, str]],
    meta: dict[str, str],
    profile: CustomRulesProfile = FPA_PROFILE,
) -> list[dict[str, object]]:
    """从功能清单行构建 FPA 模板行（三级模块兜底骨架）。"""
    if current_fpa_rule_set_config() is None:
        execution = resolve_fpa_execution_config(profile.name)
        token = set_current_fpa_rule_set_config(execution.rule_set_config)
        try:
            return _build_fpa_rule_rows(rows, meta, profile=profile)
        finally:
            reset_current_fpa_rule_set_config(token)

    fpa_rows: list[dict[str, object]] = []
    seq = 1
    for group in _group_rows_by_l3(rows):
        group_rows = profile.fallback_rows_for_l3(group, meta, start_seq=seq)
        fpa_rows.extend(group_rows)
        seq += len(group_rows)
    return fpa_rows


def _read_fpa_judgement_rules_from_template(template_path: str = "") -> list[str]:
    judgement_rules: list[str] = []
    if not template_path:
        return judgement_rules
    try:
        wb = openpyxl.load_workbook(template_path, data_only=True)
        from ai_gen_reimbursement_docs.config_utils import _get_system_config_value
        appendix_sheet = _get_system_config_value('fpa_appendix_sheet', '附录1-FPA评估方法说明')
        ws = wb[appendix_sheet]
        for row_num in range(2, ws.max_row + 1):
            val = ws.cell(row_num, 3).value
            if val and str(val).strip():
                judgement_rules.append(str(val).strip())
        wb.close()
        if judgement_rules:
            logger.debug("从模板附录读取判定原则 %d 条", len(judgement_rules))
    except Exception as e:
        logger.warning("从模板附录读取判定原则失败: %s", e)
    return judgement_rules


def _read_fpa_judgement_rules(template_path: str = "") -> list[str]:
    from ai_gen_reimbursement_docs.config_utils import (
        load_fpa_judgement_rules_config,
        load_fpa_judgement_rules_source,
    )

    source = load_fpa_judgement_rules_source()
    if source == "config":
        return load_fpa_judgement_rules_config()
    return _read_fpa_judgement_rules_from_template(template_path)


def _extract_json_obj(resp: str) -> dict[str, Any]:
    from ai_gen_reimbursement_docs.llm_client import strip_markdown_code_block

    clean = strip_markdown_code_block(resp or "").strip()
    try:
        data = _json.loads(clean)
    except _json.JSONDecodeError:
        start = clean.find("{")
        end = clean.rfind("}")
        if start < 0 or end <= start:
            raise
        data = _json.loads(clean[start:end + 1])
    if isinstance(data, list):
        data = {"rows": data}
    if not isinstance(data, dict):
        raise ValueError("AI 响应 JSON 根节点必须是对象或数组")
    return data


def _row_rule_hits(row: dict[str, object]) -> list[dict[str, object]]:
    hits = row.get(RULE_HITS_KEY)
    if not isinstance(hits, list):
        return []
    return [hit for hit in hits if isinstance(hit, dict)]


def _add_rule_hit(
    row: dict[str, object],
    *,
    hit_object: str,
    rule_id: str,
    rule_desc: str,
    suggested_type: str = "",
    adopted: bool = True,
    warnings: list[str] | None = None,
) -> None:
    hits = row.setdefault(RULE_HITS_KEY, [])
    if not isinstance(hits, list):
        hits = []
        row[RULE_HITS_KEY] = hits
    hits.append({
        "hit_object": hit_object,
        "rule_id": rule_id,
        "rule_desc": rule_desc,
        "suggested_type": suggested_type,
        "adopted": "是" if adopted else "否",
        "warnings": list(warnings or []),
    })


def _attach_profile_rule_hits(
    rows: list[dict[str, object]],
    *,
    profile: CustomRulesProfile,
    generation: str = "",
) -> None:
    """给规则生成行补充生成期命中信息，避免审核副本只靠落表后反推。"""
    for row in rows:
        if generation:
            row["生成方式"] = generation
        row_generation = str(row.get("生成方式", "") or generation or "fallback")
        if _row_rule_hits(row):
            continue
        name = str(row.get("新增/修改功能点", "") or "")
        fpa_type = str(row.get("类型", "") or "")
        reason = str(row.get("类型理由", "") or "")
        rule_id = "profile.fallback"
        if row_generation == "rules_fallback":
            rule_id = "coverage.rules_fallback"
        elif profile.name in {"unified_ui", "multi_uis"} and "界面开发" in name:
            rule_id = f"{profile.name}.ui_merge"
        elif profile.name == "strict_fpa" and fpa_type == "EIF":
            rule_id = "strict_fpa.external_data_group"
        elif profile.name == "strict_fpa" and fpa_type == "ILF":
            rule_id = "strict_fpa.internal_data_group"
        elif profile.name == "strict_fpa":
            rule_id = f"strict_fpa.transaction.{fpa_type.lower()}"
        elif "关键词" in reason or fpa_type:
            rule_id = f"{profile.name}.keyword.{fpa_type.lower()}"
        _add_rule_hit(
            row,
            hit_object=str(row.get("源功能过程", "") or name),
            rule_id=rule_id,
            rule_desc=reason or "按当前 profile 兜底规则生成。",
            suggested_type=fpa_type,
            adopted=True,
            warnings=_warning_items(row.get("后处理警告", "")),
        )


def _trace_rule_hits_for_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    trace_hits: list[dict[str, object]] = []
    for row in rows:
        for hit in _row_rule_hits(row):
            trace_hits.append({
                "fpa_seq": row.get("序号", ""),
                "name": row.get("新增/修改功能点", ""),
                "generation": row.get("生成方式", ""),
                "hit_object": hit.get("hit_object", ""),
                "rule_id": hit.get("rule_id", ""),
                "rule_desc": hit.get("rule_desc", ""),
                "suggested_type": hit.get("suggested_type", ""),
                "adopted": hit.get("adopted", ""),
                "warnings": hit.get("warnings", []),
            })
    return trace_hits


def _renumber_rows(rows: list[dict[str, object]], start_seq: int) -> None:
    for offset, row in enumerate(rows):
        row["序号"] = start_seq + offset


def _normalize_ai_fpa_name_prefix(name: str, group: dict[str, object]) -> str:
    """Force AI row names to use the module path from source data."""
    clean_name = str(name or "").strip()
    if not clean_name:
        return clean_name

    prefix = _group_tag(group).strip()
    if not prefix:
        return clean_name
    if clean_name == prefix or clean_name.startswith(f"{prefix}-"):
        return clean_name

    client_type = str(group.get("client_type", "") or "").strip()
    l1 = str(group.get("l1", "") or "").strip()
    l2 = str(group.get("l2", "") or "").strip()
    l3 = str(group.get("l3", "") or "").strip()
    path_parts = [part for part in [l1, l2, l3] if part]
    suffix = clean_name

    if path_parts:
        path_pattern = "-".join(re.escape(part) for part in path_parts)
        path_match = re.match(rf"^.*?{path_pattern}-(?P<suffix>.+)$", clean_name)
        if path_match:
            suffix = path_match.group("suffix").strip()
    if suffix == clean_name and client_type:
        client_prefixes = [client_type, f"【{client_type}】"]
        for client_prefix in client_prefixes:
            if suffix == client_prefix:
                suffix = ""
                break
            if suffix.startswith(f"{client_prefix}-"):
                suffix = suffix[len(client_prefix) + 1:].strip()
                break
    if l1 and suffix:
        path_candidate = suffix
        bracket_match = re.match(r"^【[^】]+】(?P<rest>.+)$", path_candidate)
        if bracket_match:
            path_candidate = bracket_match.group("rest").strip()
        if path_candidate.startswith(f"{l1}-"):
            parts = [part.strip() for part in path_candidate.split("-") if part.strip()]
            if len(parts) >= 4:
                suffix = "-".join(parts[3:]).strip()

    return f"{prefix}-{suffix}" if suffix else prefix


def _normalize_ai_fpa_rows_for_l3(
    *,
    group: dict[str, object],
    meta: dict[str, str],
    ai_rows: list[Any],
    judgement_rules: list[str],
    start_seq: int = 1,
    profile: CustomRulesProfile = FPA_PROFILE,
    strategy: str = "",
) -> tuple[list[dict[str, object]], list[str]]:
    warnings: list[str] = []
    subsystem = meta.get("子系统（模块）", "")
    asset = meta.get("资产标识", "")
    module_status = _module_change_status(group.get("processes", []) if isinstance(group.get("processes"), list) else [])

    ui_rows = [
        r for r in ai_rows
        if isinstance(r, dict) and "界面开发" in str(r.get("name", ""))
    ]
    if len(ui_rows) > 1 and any(not str(r.get("split_reason", "")).strip() for r in ui_rows):
        msg = f"{_group_tag(group)} AI 输出多条界面开发行但缺少 split_reason，已合并为三级模块级界面行"
        logger.warning(msg)
        warnings.append(msg)
        ai_rows = [
            profile.fallback_rows_for_l3(group, meta, start_seq=1)[0],
            *[
                r for r in ai_rows
                if not (isinstance(r, dict) and "界面开发" in str(r.get("name", "")))
            ],
        ]

    normalized: list[dict[str, object]] = []
    multi_ui_names: set[str] = set()
    seq = start_seq
    for raw in ai_rows:
        if not isinstance(raw, dict):
            warnings.append(f"{_group_tag(group)} AI rows 中存在非对象项，已跳过")
            continue
        name = str(raw.get("name", "") or raw.get("新增/修改功能点", "") or "").strip()
        if not name:
            warnings.append(f"{_group_tag(group)} AI 行缺少 name，已跳过")
            continue
        row_warnings: list[str] = []
        row_hits: list[dict[str, object]] = []
        explanation = str(raw.get("explanation", "") or raw.get("计算依据说明", "") or "").strip()
        normalized_name = profile.normalize_output_name(name, explanation)
        if normalized_name != name:
            warning = f"{_group_tag(group)} AI 行名称不符合 {profile.name} 口径，已规范化: {name} -> {normalized_name}"
            warnings.append(warning)
            row_warnings.append(warning)
            row_hits.append({
                "hit_object": name,
                "rule_id": f"{profile.name}.normalize_output_name",
                "rule_desc": f"AI 输出名称需符合 {profile.name} 口径。",
                "suggested_type": "",
                "adopted": "是",
                "warnings": [warning],
            })
            name = normalized_name
        if not explanation:
            explanation = f"{name}，具体为以下：\n1、基于该三级模块功能过程完成对应业务能力。"
            warning = f"{_group_tag(group)} AI 行缺少 explanation，已使用兜底说明: {name}"
            warnings.append(warning)
            row_warnings.append(warning)
            row_hits.append({
                "hit_object": name,
                "rule_id": "postprocess.explanation_fallback",
                "rule_desc": "AI 未提供计算依据说明时，使用兜底说明。",
                "suggested_type": "",
                "adopted": "是",
                "warnings": [warning],
            })

        ai_type = str(raw.get("type", "") or raw.get("类型", "") or "").strip().upper()
        fallback_type, fallback_reason = profile.infer_type(name, explanation)
        type_reason = str(raw.get("type_reason", "") or "").strip()
        if ai_type not in VALID_FPA_TYPES:
            if ai_type:
                warning = f"{name} AI 返回非法 type={ai_type}，已使用 {fallback_type} 兜底"
                warnings.append(warning)
                row_warnings.append(warning)
            fpa_type = fallback_type
            type_reason = type_reason or fallback_reason
            row_hits.append({
                "hit_object": name,
                "rule_id": "postprocess.invalid_ai_type",
                "rule_desc": fallback_reason or "AI type 非法时使用 profile 类型规则兜底。",
                "suggested_type": fallback_type,
                "adopted": "是",
                "warnings": row_warnings[-1:] if ai_type else [],
            })
        elif fallback_type != ai_type and profile.has_obvious_conflict(name, explanation, ai_type):
            rule_basis = fallback_reason or "规则认为 AI type 存在业务冲突。"
            conflict_detail = f"规则建议 type={fallback_type}；规则依据：{rule_basis}"
            if strategy in {"ai_first", "ai_only"}:
                warning = (
                    f"{name} AI type={ai_type} 与规则存在冲突（{conflict_detail}），"
                    f"AI 优先策略下保留 AI type={ai_type}"
                )
                warnings.append(warning)
                row_warnings.append(warning)
                fpa_type = ai_type
                type_reason = type_reason or "AI 根据功能点名称和业务说明判定。"
                row_hits.append({
                    "hit_object": name,
                    "rule_id": "postprocess.ai_first_type_conflict",
                    "rule_desc": f"{conflict_detail}；AI 优先策略保留合法 AI type。",
                    "suggested_type": fallback_type,
                    "adopted": "否",
                    "warnings": [warning],
                })
            else:
                warning = (
                    f"{name} AI type={ai_type} 与关键词规则明显冲突（{conflict_detail}），"
                    f"已使用规则建议 type={fallback_type} 兜底"
                )
                warnings.append(warning)
                row_warnings.append(warning)
                fpa_type = fallback_type
                type_reason = fallback_reason
                row_hits.append({
                    "hit_object": name,
                    "rule_id": "postprocess.keyword_type_conflict",
                    "rule_desc": f"{conflict_detail}；采用规则建议类型。",
                    "suggested_type": fallback_type,
                    "adopted": "是",
                    "warnings": [warning],
                })
        else:
            fpa_type = ai_type
            type_reason = type_reason or "AI 根据功能点名称和业务说明判定。"
            row_hits.append({
                "hit_object": name,
                "rule_id": "postprocess.ai_type_validation",
                "rule_desc": type_reason,
                "suggested_type": fpa_type,
                "adopted": "是",
                "warnings": [],
            })

        basis = ""
        idx = raw.get("classification_basis_index")
        parsed_idx: int | None = None
        if idx is not None:
            try:
                parsed_idx = int(idx)
            except (TypeError, ValueError):
                warning = f"{name} classification_basis_index 非数字: {idx}"
                warnings.append(warning)
                row_warnings.append(warning)
                row_hits.append({
                    "hit_object": name,
                    "rule_id": "postprocess.classification_basis_index",
                    "rule_desc": "classification_basis_index 必须是模板判定原则中的数字序号。",
                    "suggested_type": fpa_type,
                    "adopted": "是",
                    "warnings": [warning],
                })
        if parsed_idx is not None:
            if judgement_rules and 1 <= parsed_idx <= len(judgement_rules):
                basis = judgement_rules[parsed_idx - 1]
            else:
                warning = f"{name} classification_basis_index 越界: {parsed_idx}"
                warnings.append(warning)
                row_warnings.append(warning)
                row_hits.append({
                    "hit_object": name,
                    "rule_id": "postprocess.classification_basis_index",
                    "rule_desc": "classification_basis_index 必须落在模板判定原则范围内。",
                    "suggested_type": fpa_type,
                    "adopted": "是",
                    "warnings": [warning],
                })
        if not basis and raw.get("classification_basis"):
            val = str(raw.get("classification_basis", "")).strip()
            for rule in judgement_rules:
                if val and (val in rule or rule in val):
                    basis = rule
                    break
            if not basis:
                warning = f"{name} classification_basis 未匹配模板规则，已留空"
                warnings.append(warning)
                row_warnings.append(warning)
                row_hits.append({
                    "hit_object": name,
                    "rule_id": "postprocess.classification_basis_match",
                    "rule_desc": "classification_basis 必须能匹配模板判定原则。",
                    "suggested_type": fpa_type,
                    "adopted": "是",
                    "warnings": [warning],
                })

        review_warning = profile.ai_data_group_review_warning(name, explanation, fpa_type)
        if review_warning:
            warnings.append(review_warning)
            row_warnings.append(review_warning)
            row_hits.append({
                "hit_object": name,
                "rule_id": "postprocess.ai_data_group_review",
                "rule_desc": "AI 识别出数据功能，但当前 strict_fpa 规则无法确认数据组边界，需人工复核。",
                "suggested_type": fpa_type,
                "adopted": "是",
                "warnings": [review_warning],
            })

        explanation_warnings = _explanation_quality_warnings(
            group=group,
            name=name,
            fpa_type=fpa_type,
            explanation=explanation,
        )
        if explanation_warnings:
            warnings.extend(explanation_warnings)
            row_warnings.extend(explanation_warnings)
            row_hits.append({
                "hit_object": name,
                "rule_id": "postprocess.explanation_quality",
                "rule_desc": "计算依据说明应符合结构化证据说明规则，并将缺失信息放入 check/debug。",
                "suggested_type": fpa_type,
                "adopted": "是",
                "warnings": explanation_warnings,
            })

        id_to_name = _process_id_to_name_for_group(group)
        valid_source_ids: list[str] = []
        unknown_source_ids: list[str] = []
        raw_source_ids = raw.get("source_process_ids", [])
        if isinstance(raw_source_ids, list):
            for item in raw_source_ids:
                source_id = str(item).strip()
                if not source_id:
                    continue
                if source_id in id_to_name:
                    valid_source_ids.append(source_id)
                else:
                    unknown_source_ids.append(source_id)
        elif str(raw_source_ids or "").strip():
            unknown_source_ids.append(str(raw_source_ids).strip())

        source_processes = raw.get("source_processes", [])
        raw_source_names = (
            [str(x).strip() for x in source_processes if str(x).strip()]
            if isinstance(source_processes, list)
            else [x.strip() for x in str(source_processes or "").split("、") if x.strip()]
        )
        if unknown_source_ids:
            warning = f"{_group_tag(group)} AI 返回未知 source_process_ids: {'、'.join(unknown_source_ids)}，已忽略"
            warnings.append(warning)
            row_warnings.append(warning)
            row_hits.append({
                "hit_object": name,
                "rule_id": "postprocess.unknown_source_process_ids",
                "rule_desc": "source_process_ids 必须来自当前三级模块的功能过程候选列表。",
                "suggested_type": fpa_type,
                "adopted": "是",
                "warnings": [warning],
            })
        if not valid_source_ids and raw_source_names:
            warning = f"{_group_tag(group)} AI 未返回合法 source_process_ids，已降级使用 source_processes 名称匹配"
            warnings.append(warning)
            row_warnings.append(warning)
            row_hits.append({
                "hit_object": name,
                "rule_id": "postprocess.missing_source_process_ids",
                "rule_desc": "AI 应返回 source_process_ids；缺失时仅以 source_processes 名称作为兜底覆盖依据。",
                "suggested_type": fpa_type,
                "adopted": "是",
                "warnings": [warning],
            })
        source_names_from_ids = [id_to_name[source_id] for source_id in valid_source_ids]
        source_text = "、".join(source_names_from_ids or raw_source_names)

        output_name = _normalize_ai_fpa_name_prefix(name, group)
        if len(valid_source_ids) == 1:
            suffixed_name = _normalize_ai_name_process_suffix(
                output_name,
                id_to_name[valid_source_ids[0]],
                fpa_type,
            )
            if suffixed_name != output_name:
                warning = f"{_group_tag(group)} AI 行名称末尾已按 source_process_id 规范化: {output_name} -> {suffixed_name}"
                warnings.append(warning)
                row_warnings.append(warning)
                row_hits.append({
                    "hit_object": output_name,
                    "rule_id": "postprocess.ai_name_process_suffix",
                    "rule_desc": "AI 行保留完整功能点结构，但末尾功能过程名优先使用 source_process_id 对应的源功能过程名称。",
                    "suggested_type": "",
                    "adopted": "是",
                    "warnings": [warning],
                })
                output_name = suffixed_name
        if output_name != name:
            warning = f"{_group_tag(group)} AI 行名称前缀已按源功能清单规范化: {name} -> {output_name}"
            warnings.append(warning)
            row_warnings.append(warning)
            row_hits.append({
                "hit_object": name,
                "rule_id": "postprocess.ai_name_prefix",
                "rule_desc": "新增/修改功能点前缀必须来自源功能清单的客户端类型、一级模块、二级模块、三级模块。",
                "suggested_type": "",
                "adopted": "是",
                "warnings": [warning],
            })

        if profile.name == "multi_uis" and "界面开发" in output_name:
            split_reason = str(raw.get("split_reason", "") or "").strip()
            if split_reason:
                reason_warning = f"{output_name} multi_uis 拆分理由: {split_reason}"
                row_warnings.append(reason_warning)
                row_hits.append({
                    "hit_object": output_name,
                    "rule_id": "multi_uis.split_reason",
                    "rule_desc": "multi_uis 多界面开发行的拆分理由记录到 check/review 元数据。",
                    "suggested_type": fpa_type,
                    "adopted": "是",
                    "warnings": [reason_warning],
                })
            if output_name in multi_ui_names:
                duplicate_warning = f"{output_name} multi_uis 存在同名多界面开发行，已保留并提示人工审阅。"
                warnings.append(duplicate_warning)
                row_warnings.append(duplicate_warning)
                row_hits.append({
                    "hit_object": output_name,
                    "rule_id": "multi_uis.duplicate_ui_name",
                    "rule_desc": "multi_uis 同名多界面开发行不自动合并，保留冲突行并进入 check/review。",
                    "suggested_type": fpa_type,
                    "adopted": "是",
                    "warnings": [duplicate_warning],
                })
            multi_ui_names.add(output_name)

        row = {
            "序号": seq,
            "子系统(模块)": subsystem,
            "资产标识": asset,
            "新增/修改功能点": output_name,
            "类型": fpa_type,
            "计算依据归类": basis,
            "计算依据说明": explanation,
            "变更状态": str(raw.get("change_status", "") or module_status),
            "调整值": _adjust_value_for_type(fpa_type),
            "要素数量": int(raw.get("element_count", 1) or 1),
            "生成方式": "ai",
            "类型理由": type_reason,
            "源功能过程": source_text,
            "source_process_ids": valid_source_ids,
            "后处理警告": "；".join(row_warnings),
            "复杂度": raw.get("complexity", ""),
            "DET": raw.get("det_count", ""),
            "RET": raw.get("ret_count", ""),
            "FTR": raw.get("ftr_count", ""),
            "复杂度说明": raw.get("complexity_reason", ""),
        }
        adjustment_audit = calculate_fpa_adjustment_for_row(row)
        row["调整值"] = adjustment_audit["adjustment_value"]
        row["复杂度"] = adjustment_audit["complexity"]
        row["DET"] = adjustment_audit["det_count"]
        row["RET"] = adjustment_audit["ret_count"]
        row["FTR"] = adjustment_audit["ftr_count"]
        row["复杂度说明"] = adjustment_audit["complexity_reason"]
        row["调整值计算方式"] = adjustment_audit["method"]
        for hit in row_hits:
            _add_rule_hit(
                row,
                hit_object=str(hit.get("hit_object", "")),
                rule_id=str(hit.get("rule_id", "")),
                rule_desc=str(hit.get("rule_desc", "")),
                suggested_type=str(hit.get("suggested_type", "")),
                adopted=str(hit.get("adopted", "是")) == "是",
                warnings=hit.get("warnings", []) if isinstance(hit.get("warnings"), list) else [],
            )
        normalized.append(row)
        seq += 1
    return normalized, warnings


def _process_names_for_group(group: dict[str, object]) -> list[str]:
    processes = group.get("processes", [])
    if not isinstance(processes, list):
        return []
    return [
        str(p.get("name", "") or "").strip()
        for p in processes
        if isinstance(p, dict) and str(p.get("name", "") or "").strip()
    ]


def _process_id_to_name_for_group(group: dict[str, object]) -> dict[str, str]:
    processes = group.get("processes", [])
    if not isinstance(processes, list):
        return {}
    result: dict[str, str] = {}
    for process in processes:
        if not isinstance(process, dict):
            continue
        process_id = str(process.get("process_id", "") or "").strip()
        process_name = str(
            process.get("process_name", "") or process.get("name", "") or ""
        ).strip()
        if process_id and process_name:
            result[process_id] = process_name
    return result


def _process_name_to_id_for_group(group: dict[str, object]) -> dict[str, str]:
    return {name: process_id for process_id, name in _process_id_to_name_for_group(group).items()}


def _source_process_ids_from_row(row: dict[str, object]) -> set[str]:
    source_ids = row.get("source_process_ids", [])
    if isinstance(source_ids, list):
        return {str(item).strip() for item in source_ids if str(item).strip()}
    if isinstance(source_ids, str):
        return {item.strip() for item in re.split(r"[、,，;；\s]+", source_ids) if item.strip()}
    return set()


def _source_process_set(row: dict[str, object]) -> set[str]:
    raw = str(row.get("源功能过程", "") or "")
    return {item.strip() for item in raw.split("、") if item.strip()}


def _append_row_warning(row: dict[str, object], warning: str) -> None:
    clean_warning = str(warning or "").strip()
    if not clean_warning:
        return
    existing = _warning_items(row.get("后处理警告", ""))
    if clean_warning in existing:
        return
    row["后处理警告"] = "；".join([*existing, clean_warning])


def _apply_fpa_validation_issues(
    rows: list[dict[str, object]],
    issues: list[FpaValidationIssue],
) -> list[str]:
    warnings: list[str] = []
    for issue in issues:
        if issue.message in warnings:
            continue
        warnings.append(issue.message)
        if issue.row_index is None or not (0 <= issue.row_index < len(rows)):
            continue
        row = rows[issue.row_index]
        _append_row_warning(row, issue.message)
        _add_rule_hit(
            row,
            hit_object=str(row.get("新增/修改功能点", "") or ""),
            rule_id=issue.code,
            rule_desc="gen-fpa 输出稳定性 validator 命中项目口径检查。",
            suggested_type=str(row.get("类型", "") or ""),
            adopted=True,
            warnings=[issue.message],
        )
    return warnings


def _validate_fpa_rows_for_l3(
    *,
    group: dict[str, object],
    rows: list[dict[str, object]],
) -> tuple[list[FpaValidationIssue], list[str]]:
    issues = validate_fpa_rows(group=group, rows=rows)
    warnings = _apply_fpa_validation_issues(rows, issues)
    return issues, warnings


def _covered_process_ids_for_row(row: dict[str, object], group: dict[str, object]) -> set[str]:
    """Prefer internal process IDs, falling back to exact source-process names."""
    valid_ids = set(_process_id_to_name_for_group(group))
    row_ids = _source_process_ids_from_row(row) & valid_ids
    if row_ids:
        return row_ids
    name_to_id = _process_name_to_id_for_group(group)
    return {
        name_to_id[name]
        for name in _source_process_set(row)
        if name in name_to_id
    }


def _is_similar_process_name(left: str, right: str) -> bool:
    clean_left = re.sub(r"\s+", "", str(left or ""))
    clean_right = re.sub(r"\s+", "", str(right or ""))
    if not clean_left or not clean_right:
        return False
    if clean_left == clean_right:
        return True
    return abs(len(clean_left) - len(clean_right)) <= 4 and SequenceMatcher(None, clean_left, clean_right).ratio() >= 0.75


def _normalize_ai_name_process_suffix(name: str, source_name: str, fpa_type: str) -> str:
    if fpa_type in {"ILF", "EIF"}:
        return name
    clean_name = str(name or "").strip()
    clean_source = str(source_name or "").strip()
    if not clean_name or not clean_source:
        return clean_name
    parts = clean_name.rsplit("-", 1)
    suffix = parts[-1].strip()
    if not suffix or suffix == clean_source or not _is_similar_process_name(suffix, clean_source):
        return clean_name
    return f"{parts[0]}-{clean_source}" if len(parts) == 2 else clean_source


def _supplement_ai_rows_with_rules(
    *,
    group: dict[str, object],
    meta: dict[str, str],
    ai_rows: list[dict[str, object]],
    profile: CustomRulesProfile,
    strategy: str,
    rule_set_config: FpaRuleSetConfig | None = None,
) -> tuple[list[dict[str, object]], list[str]]:
    """AI 优先策略下，用规则补齐 AI 没覆盖的功能过程，不覆盖 AI 已判定的类型。"""
    if strategy != "ai_first" or not ai_rows:
        return ai_rows, []
    coverage_rules = rule_set_config.coverage_rules if isinstance(rule_set_config, FpaRuleSetConfig) else None
    require_process_coverage = True if coverage_rules is None or coverage_rules.require_process_coverage is None else coverage_rules.require_process_coverage
    require_data_function = True if coverage_rules is None or coverage_rules.require_data_function is None else coverage_rules.require_data_function
    if not require_process_coverage and not require_data_function:
        return ai_rows, []

    rule_rows = profile.fallback_rows_for_l3(group, meta, start_seq=1)
    id_to_name = _process_id_to_name_for_group(group)
    expected_process_ids = set(id_to_name)
    expected_process_names = set(_process_names_for_group(group))
    covered_process_ids: set[str] = set()
    covered_process_names: set[str] = set()
    for row in ai_rows:
        covered_process_ids.update(_covered_process_ids_for_row(row, group))
        covered_process_names.update(_source_process_set(row))

    if expected_process_ids:
        missing_process_ids = expected_process_ids - covered_process_ids
        missing_processes = {id_to_name[process_id] for process_id in missing_process_ids}
    else:
        missing_processes = expected_process_names - covered_process_names
    has_data_function = any(str(row.get("类型", "")) in {"ILF", "EIF"} for row in ai_rows)
    supplemental: list[dict[str, object]] = []
    data_function_supplements = 0
    missing_process_supplements = 0

    for row in rule_rows:
        row_type = str(row.get("类型", ""))
        row_sources = _source_process_set(row)
        include_data_row = require_data_function and row_type in {"ILF", "EIF"} and not has_data_function
        include_missing_process = require_process_coverage and bool(row_sources & missing_processes)
        if not include_data_row and not include_missing_process:
            continue

        copied = dict(row)
        copied["生成方式"] = "rules_fallback"
        reason = str(copied.get("类型理由", "") or "")
        if include_missing_process:
            missing_process_supplements += 1
        if include_data_row:
            data_function_supplements += 1
        copied["类型理由"] = reason or (
            "AI 未包含数据功能行，按规则集补齐。"
            if include_data_row and not include_missing_process
            else "AI 未覆盖该功能过程，按规则集补齐。"
        )
        warning = (
            "AI 结果未包含数据功能行，已按规则集补齐；未覆盖 AI 已判定类型。"
            if include_data_row and not include_missing_process
            else "AI 结果未覆盖该功能过程，已按规则集补齐；未覆盖 AI 已判定类型。"
        )
        old_warning = str(copied.get("后处理警告", "") or "")
        copied["后处理警告"] = f"{old_warning}；{warning}" if old_warning else warning
        _attach_profile_rule_hits([copied], profile=profile, generation="rules_fallback")
        supplemental.append(copied)

    if not supplemental:
        return ai_rows, []

    combined = [*ai_rows, *supplemental]
    for seq, row in enumerate(combined, 1):
        row["序号"] = seq
    warning_parts: list[str] = []
    if missing_process_supplements:
        warning_parts.append(f"AI 结果未覆盖 {len(missing_processes)} 个功能过程")
    if data_function_supplements:
        warning_parts.append("AI 结果未包含数据功能行")
    reason = "，".join(warning_parts) or "AI 结果需要规则补齐"
    warnings = [f"{_group_tag(group)} {reason}，已追加 {len(supplemental)} 条 rules_fallback 行"]
    return combined, warnings


def _rules_first_ai_reasons(group: dict[str, object], rule_rows: list[dict[str, object]]) -> list[str]:
    """Return reasons why rules_first should ask AI to re-plan this module."""
    reasons: list[str] = []
    if not rule_rows:
        reasons.append("规则未生成 FPA 行")
        return reasons

    for index, row in enumerate(rule_rows, 1):
        name = str(row.get("新增/修改功能点", "") or "").strip()
        fpa_type = str(row.get("类型", "") or "").strip()
        if not name:
            reasons.append(f"规则行 {index} 新增/修改功能点为空")
        if fpa_type not in VALID_FPA_TYPES:
            reasons.append(f"规则行 {index} 类型无效: {fpa_type or '空'}")

    expected = set(_process_names_for_group(group))
    covered: set[str] = set()
    for row in rule_rows:
        covered.update(_source_process_set(row))
    missing = sorted(expected - covered)
    if missing:
        reasons.append(f"规则结果未覆盖功能过程: {'、'.join(missing)}")
    return reasons


def _build_fpa_audit_report(
    *,
    group: dict[str, object],
    module: dict[str, object],
    fpa_rows: list[dict[str, object]],
    warnings: list[str],
    profile: CustomRulesProfile,
    profile_version: str,
    strategy: str,
    rule_set: str,
    raw_source: str = "",
    raw_rows: list[object] | None = None,
    raw_warnings: list[str] | None = None,
    rule_hits: list[dict[str, object]] | None = None,
) -> FpaAuditReport:
    process_names = _process_names_for_group(group)
    id_to_name = _process_id_to_name_for_group(group)
    expected_ids = set(id_to_name)
    covered_ids: set[str] = set()
    covered_names: set[str] = set()
    generation_counts: dict[str, int] = {}
    for row in fpa_rows:
        generation = str(row.get("生成方式", "") or "unknown")
        generation_counts[generation] = generation_counts.get(generation, 0) + 1
        covered_ids.update(_covered_process_ids_for_row(row, group))
        covered_names.update(_source_process_set(row))

    if expected_ids:
        covered_processes = [name for process_id, name in id_to_name.items() if process_id in covered_ids]
        missing_processes = [name for process_id, name in id_to_name.items() if process_id not in covered_ids]
    else:
        covered_processes = [name for name in process_names if name in covered_names]
        missing_processes = [name for name in process_names if name not in covered_names]
    audit_warnings = list(warnings)
    if process_names and missing_processes:
        audit_warnings.append(f"仍有 {len(missing_processes)} 个功能过程未被 FPA 行覆盖")

    return FpaAuditReport(
        profile=profile.name,
        profile_version=profile_version,
        strategy=strategy,
        rule_set=rule_set,
        module=module,
        process_total=len(process_names),
        covered_processes=covered_processes,
        missing_processes=missing_processes,
        generation_counts=generation_counts,
        warnings=audit_warnings,
        raw_source=raw_source,
        raw_rows=list(raw_rows or []),
        raw_warnings=list(raw_warnings or []),
        rule_hits=list(rule_hits or []),
    )


def _module_payload_for_audit(index: int, group: dict[str, object]) -> dict[str, object]:
    processes = group.get("processes", [])
    process_count = len(processes) if isinstance(processes, list) else 0
    return {
        "index": index,
        "client_type": group.get("client_type", ""),
        "l1": group.get("l1", ""),
        "l2": group.get("l2", ""),
        "l3": group.get("l3", ""),
        "process_count": process_count,
    }


def _audit_rule_hits_for_rows(
    rows: list[dict[str, object]],
    traced_hits_by_seq: dict[str, list[dict[str, object]]],
    group: dict[str, object],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for row in rows:
        row_seq = str(row.get("序号", "") or "")
        traced_hits = traced_hits_by_seq.get(row_seq, [])
        if not traced_hits:
            rule_id, rule_desc = _rule_hit_for_audit(row)
            traced_hits = [{
                "hit_object": row.get("源功能过程", "") or group.get("l3", ""),
                "rule_id": rule_id,
                "rule_desc": rule_desc,
                "suggested_type": row.get("类型", ""),
                "adopted": "是",
                "warnings": _warning_items(row.get("后处理警告", "")),
            }]
        for hit in traced_hits:
            result.append({
                "fpa_seq": row.get("序号", ""),
                "function_point": row.get("新增/修改功能点", ""),
                "generation": row.get("生成方式", ""),
                "hit_object": hit.get("hit_object", "") or row.get("源功能过程", "") or group.get("l3", ""),
                "rule_id": hit.get("rule_id", ""),
                "rule_desc": hit.get("rule_desc", ""),
                "suggested_type": hit.get("suggested_type", "") or row.get("类型", ""),
                "adopted": hit.get("adopted", "") or "是",
                "warnings": hit.get("warnings", []) if isinstance(hit.get("warnings", []), list) else [],
            })
    return result


def _build_fpa_audit_reports_for_groups(
    *,
    groups: list[dict[str, object]],
    rows_by_module: dict[int, list[dict[str, object]]],
    warnings_by_module: dict[int, list[str]],
    profile: CustomRulesProfile,
    profile_version: str,
    strategy: str,
    rule_set: str,
    raw_audit_by_module: dict[int, dict[str, object]] | None = None,
    rule_hits_by_seq: dict[str, list[dict[str, object]]] | None = None,
) -> list[FpaAuditReport]:
    reports: list[FpaAuditReport] = []
    raw_audit_by_module = raw_audit_by_module or {}
    rule_hits_by_seq = rule_hits_by_seq or {}
    for idx, group in enumerate(groups, 1):
        rows = rows_by_module.get(idx, [])
        raw_audit = raw_audit_by_module.get(idx, {})
        raw_warnings = raw_audit.get("warnings", [])
        reports.append(_build_fpa_audit_report(
            group=group,
            module=_module_payload_for_audit(idx, group),
            fpa_rows=rows,
            warnings=warnings_by_module.get(idx, []),
            profile=profile,
            profile_version=profile_version,
            strategy=strategy,
            rule_set=rule_set,
            raw_source=str(raw_audit.get("source", "") or ""),
            raw_rows=raw_audit.get("raw_rows", []) if isinstance(raw_audit.get("raw_rows", []), list) else [],
            raw_warnings=raw_warnings if isinstance(raw_warnings, list) else _warning_items(raw_warnings),
            rule_hits=_audit_rule_hits_for_rows(rows, rule_hits_by_seq, group),
        ))
    return reports


def _rule_set_config_warnings(rule_set_config: object | None) -> list[str]:
    if isinstance(rule_set_config, FpaRuleSetConfig):
        return list(rule_set_config.config_warnings)
    return []


def _with_config_warnings(warnings: list[str], rule_set_config: object | None) -> list[str]:
    merged = list(_rule_set_config_warnings(rule_set_config))
    merged.extend(warnings)
    return merged


def _is_config_warning(warning: object) -> bool:
    return str(warning or "").strip().startswith(CONFIG_WARNING_PREFIX)


class FpaAiDebugError(ValueError):
    """FPA 预览 AI 调试信息异常。"""

    def __init__(self, message: str, debug: dict[str, object]):
        super().__init__(message)
        self.debug = debug


def _build_fpa_ai_prompt_context(
    group: dict[str, object],
    judgement_rules: list[str],
    domain_context: dict[str, object] | None,
    profile: CustomRulesProfile = FPA_PROFILE,
) -> FpaPromptContext:
    from ai_gen_reimbursement_docs.config_utils import (
        load_fpa_core_rules_config,
        load_fpa_system_prompt_config,
        load_fpa_user_prompt_config,
    )

    core_rules_config = load_fpa_core_rules_config(profile.name)
    system_config = load_fpa_system_prompt_config(profile.name)
    user_config = load_fpa_user_prompt_config(profile.name)
    prompt = profile.build_prompt(group, judgement_rules, domain_context)
    return FpaPromptContext(
        system_prompt=system_config.text,
        user_prompt=prompt,
        core_rules=core_rules_config.text,
        core_rules_source=core_rules_config.source_label,
        system_prompt_source=system_config.source_label,
        user_prompt_source=user_config.source_label,
    )


def _ai_plan_fpa_rows_for_l3_debug(
    group: dict[str, object],
    judgement_rules: list[str],
    domain_context: dict[str, object] | None,
    api_key: str,
    model: str,
    base_url: str,
    profile: CustomRulesProfile = FPA_PROFILE,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """调用 AI 规划一个三级模块的 FPA 行，并返回 Web 预览调试信息。"""
    prompt_context = _build_fpa_ai_prompt_context(
        group, judgement_rules, domain_context, profile
    )
    debug: dict[str, object] = {
        "ai_called": True,
        "model": model,
        "system_prompt": prompt_context.system_prompt,
        "system_prompt_source": prompt_context.system_prompt_source,
        "user_prompt": prompt_context.user_prompt,
        "user_prompt_source": prompt_context.user_prompt_source,
        "core_rules_source": prompt_context.core_rules_source,
        "ai_prompt": f"[system]\n{prompt_context.system_prompt}\n\n[user]\n{prompt_context.user_prompt}",
        "raw_response": "",
        "thinking": "",
        "parsed_rows": [],
    }
    resp, thinking = _call_llm(
        prompt_context.user_prompt,
        prompt_context.system_prompt,
        api_key,
        model,
        base_url,
        tag=f"fpa_l3_{group.get('l3', '')}",
        return_thinking=True,
    )
    debug["raw_response"] = resp
    debug["thinking"] = thinking
    if not resp:
        raise FpaAiDebugError("LLM 返回空响应", debug)
    try:
        data = _extract_json_obj(resp)
    except Exception as exc:
        raise FpaAiDebugError(str(exc), debug) from exc
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise FpaAiDebugError("AI 响应缺少 rows 列表", debug)
    debug["parsed_rows"] = rows
    return rows, debug


def _ai_plan_fpa_rows_for_l3(
    group: dict[str, object],
    judgement_rules: list[str],
    domain_context: dict[str, object] | None,
    api_key: str,
    model: str,
    base_url: str,
    profile: CustomRulesProfile = FPA_PROFILE,
    validation_retry_feedback: str = "",
) -> list[dict[str, object]]:
    """调用 AI 规划一个三级模块的 FPA 行，返回原始 AI rows。"""
    prompt_context = _build_fpa_ai_prompt_context(
        group, judgement_rules, domain_context, profile
    )
    user_prompt = prompt_context.user_prompt
    if validation_retry_feedback:
        user_prompt = f"{user_prompt}\n\n{validation_retry_feedback}"
    resp = _call_llm(
        user_prompt,
        prompt_context.system_prompt,
        api_key,
        model,
        base_url,
        tag=f"fpa_l3_{group.get('l3', '')}",
    )
    if not resp:
        raise ValueError("LLM 返回空响应")
    data = _extract_json_obj(resp)
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise ValueError("AI 响应缺少 rows 列表")
    return rows


def _build_domain_context(meta: dict[str, str]) -> dict[str, object]:
    from ai_gen_reimbursement_docs.config_utils import load_optional_fpa_domain_context

    keys = [
        "子系统（模块）",
        "资产标识",
        "新增/修改功能点前缀生成规则",
        "功能用户-接收者判定",
    ]
    context = {k: meta.get(k, "") for k in keys if meta.get(k)}
    configured_context = dict(load_optional_fpa_domain_context())
    configured_context.pop("project_description", None)
    context.update(configured_context)
    project_description = _build_project_description_from_work_order(meta)
    if project_description:
        context["project_description"] = project_description
    return context


def _first_meta_value(meta: dict[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(meta.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _build_project_description_from_work_order(meta: dict[str, str]) -> str:
    title = _first_meta_value(meta, ("工单标题", "1、工单需求-元数据录入.工单标题"))
    content = _first_meta_value(meta, ("工单内容", "1、工单需求-元数据录入.工单内容"))
    parts: list[str] = []
    if title:
        parts.append(f"工单标题：{title}")
    if content:
        parts.append(f"工单内容：{content}")
    description = "\n".join(parts).strip()
    if len(description) <= FPA_PROJECT_DESCRIPTION_MAX_CHARS:
        return description
    truncated = description[:FPA_PROJECT_DESCRIPTION_MAX_CHARS].rstrip()
    return f"{truncated}\n（工单内容已截断，完整内容以功能清单录入模板为准。）"


def _fpa_ai_cache_key(
    group: dict[str, object],
    judgement_rules: list[str],
    domain_context: dict[str, object],
    model: str,
    profile: CustomRulesProfile = FPA_PROFILE,
    strategy: str = "",
    rule_set: str = "",
    rule_set_config: object | None = None,
    core_rules: str = "",
    system_prompt: str = "",
    user_prompt: str = "",
) -> str:
    serializable_rule_set_config = (
        rule_set_config.raw if isinstance(rule_set_config, FpaRuleSetConfig) else rule_set_config or {}
    )
    payload = {
        "profile": profile.name,
        "profile_version": profile.version,
        "strategy": strategy,
        "rule_set": rule_set,
        "rule_set_config": serializable_rule_set_config,
        "core_rules": core_rules,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "domain_context": domain_context,
        "group": group,
        "judgement_rules": judgement_rules,
        "model": model,
    }
    raw = _json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_fpa_ai_cache(cache_path: str) -> dict[str, object]:
    if not cache_path or not os.path.exists(cache_path):
        return {"version": 1, "entries": {}}
    try:
        with open(cache_path, encoding="utf-8") as f:
            data = _json.load(f)
        if not isinstance(data, dict):
            raise ValueError("cache root must be object")
        entries = data.get("entries")
        if not isinstance(entries, dict):
            data["entries"] = {}
        data["version"] = 1
        return data
    except Exception as exc:
        logger.warning("FPA AI 缓存读取失败，将忽略缓存: %s", exc)
        return {"version": 1, "entries": {}}


def _save_fpa_ai_cache(cache_path: str, cache: dict[str, object]) -> None:
    if not cache_path:
        return
    try:
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            _json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("FPA AI 缓存写入失败: %s", exc)


def _save_fpa_audit_trace(audit_trace_path: str, trace: dict[str, object]) -> None:
    if not audit_trace_path:
        return
    try:
        os.makedirs(os.path.dirname(audit_trace_path) or ".", exist_ok=True)
        with open(audit_trace_path, "w", encoding="utf-8") as f:
            _json.dump(trace, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("FPA audit trace 写入失败: %s", exc)


def _load_fpa_audit_trace(audit_trace_path: str) -> dict[str, object]:
    if not audit_trace_path or not os.path.exists(audit_trace_path):
        return {}
    try:
        with open(audit_trace_path, encoding="utf-8") as f:
            data = _json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("FPA audit trace 读取失败: %s", exc)
        return {}


def _as_float(value: object) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def calculate_fpa_row_workload(row: dict[str, object]) -> float:
    """按代码化业务口径计算单行 FPA 工作量。"""
    return _as_float(row.get("调整值")) * _as_float(row.get("要素数量"))


def calculate_fpa_total(rows: list[dict[str, object]]) -> float:
    """按代码化业务口径计算 FPA 工作量总和。"""
    return sum(calculate_fpa_row_workload(row) for row in rows)


def _enrich_fpa_rows_with_adjustment(rows: list[dict[str, object]]) -> None:
    """Apply configured adjustment calculation and audit fields to rows in place."""
    for row in rows:
        adjustment_audit = calculate_fpa_adjustment_for_row(row)
        row["调整值"] = adjustment_audit["adjustment_value"]
        row["复杂度"] = adjustment_audit["complexity"]
        row["DET"] = adjustment_audit["det_count"]
        row["RET"] = adjustment_audit["ret_count"]
        row["FTR"] = adjustment_audit["ftr_count"]
        row["复杂度说明"] = adjustment_audit["complexity_reason"]
        row["调整值计算方式"] = adjustment_audit["method"]


def calculate_fpa_excel_formula_projection(xlsx_path: str) -> float:
    """读取 Excel 公式输入列，确定性投影 L 列工作量总和。"""
    from ai_gen_reimbursement_docs.config_utils import _get_system_config_value

    wb = openpyxl.load_workbook(xlsx_path, data_only=False)
    try:
        sheet_name = _get_system_config_value("fpa_sheet", "FPA功能点估算")
        ws = wb[sheet_name]
        last_data_row = ws.max_row
        expected_total_formula = f"=SUM(L3:L{last_data_row})"
        if ws.cell(1, FPA_COL_FORMULA_WORKLOAD).value != expected_total_formula:
            raise ValueError(f"FPA Excel 汇总公式无效，应为 {expected_total_formula}")

        total = 0.0
        for row_num in range(3, last_data_row + 1):
            expected_row_formula = f"=J{row_num}*K{row_num}"
            if ws.cell(row_num, FPA_COL_FORMULA_WORKLOAD).value != expected_row_formula:
                raise ValueError(f"FPA Excel 第 {row_num} 行工作量公式无效，应为 {expected_row_formula}")
            total += _as_float(ws.cell(row_num, FPA_COL_ADJUST).value) * _as_float(
                ws.cell(row_num, FPA_COL_ELEMENTS).value
            )
        return total
    finally:
        wb.close()


def _recalculate_with_excel_com(xlsx_path: str) -> tuple[bool, str]:
    """Use local Excel COM to recalculate and save formula caches."""
    if os.name != "nt":
        return False, "Excel COM 仅支持 Windows"
    try:
        import win32com.client  # type: ignore
    except Exception as exc:
        return False, f"Excel COM 不可用: {exc}"

    excel = None
    workbook = None
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        workbook = excel.Workbooks.Open(os.path.abspath(xlsx_path))
        excel.CalculateFullRebuild()
        workbook.Save()
        return True, "Excel COM"
    except Exception as exc:
        return False, f"Excel COM 复算失败: {exc}"
    finally:
        if workbook is not None:
            try:
                workbook.Close(SaveChanges=True)
            except Exception:
                pass
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass


def _recalculate_with_libreoffice(xlsx_path: str) -> tuple[bool, str]:
    """Use LibreOffice/soffice headless conversion to recalculate formula caches."""
    executable = shutil.which("soffice") or shutil.which("libreoffice")
    if not executable:
        return False, "未找到 LibreOffice/soffice"
    with tempfile.TemporaryDirectory(prefix="ard-fpa-recalc-") as tmp_dir:
        completed = subprocess.run(
            [
                executable,
                "--headless",
                "--convert-to",
                "xlsx",
                "--outdir",
                tmp_dir,
                os.path.abspath(xlsx_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            return False, f"LibreOffice 复算失败: {detail or completed.returncode}"
        recalculated = os.path.join(tmp_dir, os.path.basename(xlsx_path))
        if not os.path.exists(recalculated):
            return False, "LibreOffice 未生成复算后的 xlsx"
        shutil.copy2(recalculated, xlsx_path)
    return True, "LibreOffice"


def _read_fpa_excel_cached_total(xlsx_path: str) -> float | None:
    from ai_gen_reimbursement_docs.config_utils import _get_system_config_value

    sheet_name = _get_system_config_value('fpa_sheet', 'FPA功能点估算')
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    try:
        ws = wb[sheet_name]
        value = ws.cell(1, FPA_COL_FORMULA_WORKLOAD).value
    finally:
        wb.close()
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def validate_fpa_excel_recalculation(
    xlsx_path: str,
    expected_total: float,
    tolerance: float = 0.01,
) -> list[str]:
    """Try to recalculate FPA Excel formulas and return non-blocking warnings."""
    attempts: list[str] = []
    for recalculator in (_recalculate_with_excel_com, _recalculate_with_libreoffice):
        ok, message = recalculator(xlsx_path)
        if not ok:
            attempts.append(message)
            continue

        cached_total = _read_fpa_excel_cached_total(xlsx_path)
        if cached_total is None:
            return [f"FPA Excel 公式复算已执行（{message}），但无法读取 L1 缓存总工作量"]
        if abs(cached_total - expected_total) > tolerance:
            return [
                "FPA Excel 公式复算结果与代码汇总不一致: "
                f"Excel={cached_total}, 代码汇总={expected_total}"
            ]
        return []

    return [f"未执行 FPA Excel 公式复算校验: {'；'.join(attempts)}"]


def write_fpa_summary_md(summary_md_path: str, total: float) -> None:
    os.makedirs(os.path.dirname(summary_md_path) or '.', exist_ok=True)
    with open(summary_md_path, 'w', encoding='utf-8') as f:
        f.write("# FPA 工作量\n\n")
        f.write(f"FPA工作量（人/天）: {total}\n")


def _plan_fpa_rows_with_ai(
    rows: list[dict[str, str]],
    meta: dict[str, str],
    judgement_rules: list[str],
    api_key: str,
    model: str,
    base_url: str,
    cache_path: str = "",
    profile: CustomRulesProfile = FPA_PROFILE,
    strategy: str = "",
    rule_set: str = "",
    rule_set_config: object | None = None,
    audit_trace_path: str = "",
) -> list[dict[str, object]]:
    execution = resolve_fpa_execution_config(profile.name, strategy, rule_set)
    profile = execution.profile
    strategy = execution.strategy
    rule_set = execution.rule_set
    effective_rule_set_config = rule_set_config if isinstance(rule_set_config, FpaRuleSetConfig) else execution.rule_set_config
    rule_set_token = set_current_fpa_rule_set_config(effective_rule_set_config)
    try:
        return _plan_fpa_rows_with_execution(
            rows,
            meta,
            judgement_rules,
            api_key,
            model,
            base_url,
            cache_path=cache_path,
            profile=profile,
            strategy=strategy,
            rule_set=rule_set,
            rule_set_config=effective_rule_set_config,
            audit_trace_path=audit_trace_path,
        )
    finally:
        reset_current_fpa_rule_set_config(rule_set_token)


def _plan_fpa_rows_with_execution(
    rows: list[dict[str, str]],
    meta: dict[str, str],
    judgement_rules: list[str],
    api_key: str,
    model: str,
    base_url: str,
    cache_path: str = "",
    profile: CustomRulesProfile = FPA_PROFILE,
    strategy: str = "",
    rule_set: str = "",
    rule_set_config: object | None = None,
    audit_trace_path: str = "",
) -> list[dict[str, object]]:
    groups = _group_rows_by_l3(rows)
    config_warnings = _rule_set_config_warnings(rule_set_config)
    if strategy == "rules_only":
        logger.info("FPA strategy=%s，使用规则集 %s 生成 FPA", strategy, rule_set)
        all_rows: list[dict[str, object]] = []
        audit_modules: list[dict[str, object]] = []
        seq = 1
        for group in groups:
            group_rows = profile.fallback_rows_for_l3(group, meta, start_seq=seq)
            _attach_profile_rule_hits(group_rows, profile=profile, generation="fallback")
            all_rows.extend(group_rows)
            seq += len(group_rows)
            audit_modules.append({
                "module": _group_tag(group),
                "l3": group.get("l3", ""),
                "source": "rules",
                "raw_rows": [],
                "warnings": [*config_warnings, "仅规则策略未调用 AI"],
                "rule_hits": _trace_rule_hits_for_rows(group_rows),
            })
        _save_fpa_audit_trace(audit_trace_path, {
            "version": 1,
            "profile": profile.name,
            "strategy": strategy,
            "rule_set": rule_set,
            "modules": audit_modules,
        })
        return all_rows
    if strategy != "rules_first" and not api_key:
        raise ValueError(f"FPA strategy={strategy} 需要 API Key，当前未配置")

    from ai_gen_reimbursement_docs.config_utils import FpaPromptConfigError, load_flow_max_ai, load_gen_fpa_ai_limit

    max_ai = load_flow_max_ai("gen_fpa")
    module_limit = load_gen_fpa_ai_limit()
    all_rows: list[dict[str, object]] = []
    seq = 1
    attempted = success = parse_failed = empty_response = generated = fallback = skipped = warning_count = cache_hits = 0
    domain_context = _build_domain_context(meta)
    cache = _load_fpa_ai_cache(cache_path) if cache_path else {"version": 1, "entries": {}}
    cache_entries = cache.get("entries")
    if not isinstance(cache_entries, dict):
        cache_entries = {}
        cache["entries"] = cache_entries
    audit_modules: list[dict[str, object]] = []

    for idx, group in enumerate(groups, 1):
        rules_first_rows: list[dict[str, object]] = []
        rules_first_reasons: list[str] = []
        if strategy == "rules_first":
            rules_first_rows = profile.fallback_rows_for_l3(group, meta, start_seq=seq)
            _attach_profile_rule_hits(rules_first_rows, profile=profile, generation="fallback")
            rules_first_reasons = _rules_first_ai_reasons(group, rules_first_rows)
            if not rules_first_reasons:
                logger.info("  FPA rules_first 使用规则结果 [%d/%d] %s", idx, len(groups), _group_tag(group))
                all_rows.extend(rules_first_rows)
                seq += len(rules_first_rows)
                audit_modules.append({
                    "module": _group_tag(group),
                    "l3": group.get("l3", ""),
                    "source": "rules",
                    "raw_rows": [],
                    "warnings": [*config_warnings, "规则优先策略未调用 AI：规则结果覆盖完整且基础字段有效"],
                    "rule_hits": _trace_rule_hits_for_rows(rules_first_rows),
                })
                continue
            if not api_key:
                warning = "规则结果需要 AI 复核但未配置 API Key，已保留规则生成结果: " + "；".join(rules_first_reasons)
                logger.warning("FPA rules_first 未调用 AI [%s]: %s", _group_tag(group), warning)
                all_rows.extend(rules_first_rows)
                seq += len(rules_first_rows)
                audit_modules.append({
                    "module": _group_tag(group),
                    "l3": group.get("l3", ""),
                    "source": "rules",
                    "raw_rows": [],
                    "warnings": [*config_warnings, warning],
                    "rule_hits": _trace_rule_hits_for_rows(rules_first_rows),
                })
                continue

        limited = (max_ai > 0 and idx > max_ai) or (module_limit > 0 and idx > module_limit)
        if limited:
            if strategy == "ai_only":
                raise ValueError(f"FPA strategy=ai_only 但三级模块 {_group_tag(group)} 被 AI 限制跳过")
            skipped += 1
            group_rows = rules_first_rows or profile.fallback_rows_for_l3(group, meta, start_seq=seq)
            generation = "fallback" if strategy == "rules_first" else "rules_fallback"
            _attach_profile_rule_hits(group_rows, profile=profile, generation=generation)
            fallback += len(group_rows)
            all_rows.extend(group_rows)
            seq += len(group_rows)
            warning = "模块超过 AI 调用限制，已使用规则生成"
            if rules_first_reasons:
                warning = f"规则结果需要 AI 复核但{warning}: {'；'.join(rules_first_reasons)}"
            audit_modules.append({
                "module": _group_tag(group),
                "l3": group.get("l3", ""),
                "source": "rules" if strategy == "rules_first" else "rules_fallback",
                "raw_rows": [],
                "warnings": [*config_warnings, warning],
                "rule_hits": _trace_rule_hits_for_rows(group_rows),
            })
            continue

        prompt_context = _build_fpa_ai_prompt_context(
            group, judgement_rules, domain_context, profile
        )
        cache_key = _fpa_ai_cache_key(
            group, judgement_rules, domain_context, model,
            profile=profile,
            strategy=strategy,
            rule_set=rule_set,
            rule_set_config=rule_set_config.raw if isinstance(rule_set_config, FpaRuleSetConfig) else rule_set_config or {},
            core_rules=prompt_context.core_rules,
            system_prompt=prompt_context.system_prompt,
            user_prompt=prompt_context.user_prompt,
        )
        cached = cache_entries.get(cache_key) if cache_path else None
        if isinstance(cached, dict) and isinstance(cached.get("rows"), list):
            try:
                raw_rows = cached["rows"]
                group_rows, warnings = _normalize_ai_fpa_rows_for_l3(
                    group=group,
                    meta=meta,
                    ai_rows=raw_rows,
                    judgement_rules=judgement_rules,
                    start_seq=seq,
                    profile=profile,
                    strategy=strategy,
                )
                if rules_first_reasons:
                    warnings.insert(0, "规则结果触发 AI 复核: " + "；".join(rules_first_reasons))
                group_rows, supplement_warnings = _supplement_ai_rows_with_rules(
                    group=group,
                    meta=meta,
                    ai_rows=group_rows,
                    profile=profile,
                    strategy=strategy,
                    rule_set_config=rule_set_config,
                )
                _renumber_rows(group_rows, seq)
                warnings.extend(supplement_warnings)
                validation_issues, validation_warnings = _validate_fpa_rows_for_l3(
                    group=group,
                    rows=group_rows,
                )
                warnings.extend(validation_warnings)
                if retryable_validation_issues(validation_issues):
                    logger.warning(
                        "FPA AI 缓存未通过稳定性校验 [%s]，将重新调用 AI: %s",
                        _group_tag(group),
                        "；".join(issue.message for issue in retryable_validation_issues(validation_issues)),
                    )
                    group_rows = []
                if group_rows:
                    cache_hits += 1
                    success += 1
                    generated += len(group_rows)
                    warning_count += len(warnings)
                    logger.info("  FPA AI 缓存命中 [%d/%d] %s", idx, len(groups), _group_tag(group))
                    all_rows.extend(group_rows)
                    seq += len(group_rows)
                    audit_modules.append({
                        "module": _group_tag(group),
                        "l3": group.get("l3", ""),
                        "source": "ai_cache",
                        "raw_rows": raw_rows,
                        "warnings": _with_config_warnings(warnings, rule_set_config),
                        "rule_hits": _trace_rule_hits_for_rows(group_rows),
                    })
                    continue
            except Exception as exc:
                logger.warning("FPA AI 缓存内容无效 [%s]: %s，将重新调用 AI", _group_tag(group), exc)

        attempted += 1
        try:
            logger.info("  FPA AI 规划三级模块 [%d/%d] %s", idx, len(groups), _group_tag(group))
            raw_rows = _ai_plan_fpa_rows_for_l3(
                group, judgement_rules, domain_context, api_key, model, base_url, profile=profile
            )
            group_rows, warnings = _normalize_ai_fpa_rows_for_l3(
                group=group,
                meta=meta,
                ai_rows=raw_rows,
                judgement_rules=judgement_rules,
                start_seq=seq,
                profile=profile,
                strategy=strategy,
            )
            if rules_first_reasons:
                warnings.insert(0, "规则结果触发 AI 复核: " + "；".join(rules_first_reasons))
            group_rows, supplement_warnings = _supplement_ai_rows_with_rules(
                group=group,
                meta=meta,
                ai_rows=group_rows,
                profile=profile,
                strategy=strategy,
                rule_set_config=rule_set_config,
            )
            _renumber_rows(group_rows, seq)
            warnings.extend(supplement_warnings)
            validation_issues, validation_warnings = _validate_fpa_rows_for_l3(
                group=group,
                rows=group_rows,
            )
            warnings.extend(validation_warnings)
            retry_feedback = validation_feedback(validation_issues)
            if retry_feedback and strategy == "ai_first":
                logger.warning("FPA AI 输出触发稳定性重试 [%s]", _group_tag(group))
                retry_raw_rows = _ai_plan_fpa_rows_for_l3(
                    group,
                    judgement_rules,
                    domain_context,
                    api_key,
                    model,
                    base_url,
                    profile=profile,
                    validation_retry_feedback=retry_feedback,
                )
                retry_group_rows, retry_warnings = _normalize_ai_fpa_rows_for_l3(
                    group=group,
                    meta=meta,
                    ai_rows=retry_raw_rows,
                    judgement_rules=judgement_rules,
                    start_seq=seq,
                    profile=profile,
                    strategy=strategy,
                )
                if rules_first_reasons:
                    retry_warnings.insert(0, "规则结果触发 AI 复核: " + "；".join(rules_first_reasons))
                retry_group_rows, retry_supplement_warnings = _supplement_ai_rows_with_rules(
                    group=group,
                    meta=meta,
                    ai_rows=retry_group_rows,
                    profile=profile,
                    strategy=strategy,
                    rule_set_config=rule_set_config,
                )
                _renumber_rows(retry_group_rows, seq)
                retry_warnings.extend(retry_supplement_warnings)
                retry_issues, retry_validation_warnings = _validate_fpa_rows_for_l3(
                    group=group,
                    rows=retry_group_rows,
                )
                retry_warnings.extend(retry_validation_warnings)
                retry_notice = f"{_group_tag(group)} AI 输出稳定性校验触发一次重试"
                if retry_group_rows:
                    raw_rows = retry_raw_rows
                    group_rows = retry_group_rows
                    warnings = [retry_notice, *retry_warnings]
                    if retryable_validation_issues(retry_issues):
                        warnings.append(
                            f"{_group_tag(group)} AI 重试后仍存在稳定性 warning: "
                            + "；".join(issue.message for issue in retryable_validation_issues(retry_issues))
                        )
                else:
                    warnings.append(f"{retry_notice}，但重试未生成有效 FPA 行，保留首次结果")
            warning_count += len(warnings)
            if not group_rows:
                raise ValueError("AI 规划未生成有效 FPA 行")
            success += 1
            generated += len(group_rows)
            if cache_path:
                cache_entries[cache_key] = {
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "model": model,
                    "profile": profile.name,
                    "profile_version": profile.version,
                    "strategy": strategy,
                    "rule_set": rule_set,
                    "rows": raw_rows,
                }
            audit_modules.append({
                "module": _group_tag(group),
                "l3": group.get("l3", ""),
                "source": "ai",
                "raw_rows": raw_rows,
                "warnings": _with_config_warnings(warnings, rule_set_config),
                "rule_hits": _trace_rule_hits_for_rows(group_rows),
            })
        except FpaPromptConfigError:
            raise
        except Exception as exc:
            if strategy == "ai_only":
                raise
            msg = str(exc)
            if "空响应" in msg:
                empty_response += 1
            else:
                parse_failed += 1
            logger.warning("FPA AI 响应解析失败 [%s]: %s", _group_tag(group), exc)
            group_rows = rules_first_rows or profile.fallback_rows_for_l3(group, meta, start_seq=seq)
            _attach_profile_rule_hits(group_rows, profile=profile, generation="fallback")
            fallback += len(group_rows)
            fallback_warning = f"AI 调用或解析失败: {exc}"
            if rules_first_reasons:
                fallback_warning = (
                    "规则结果触发 AI 复核，但 AI 调用或解析失败，已保留规则生成结果: "
                    + "；".join(rules_first_reasons)
                    + f"；AI错误: {exc}"
                )
            audit_modules.append({
                "module": _group_tag(group),
                "l3": group.get("l3", ""),
                "source": "rules_fallback",
                "raw_rows": locals().get("raw_rows", []),
                "warnings": [*config_warnings, fallback_warning],
                "rule_hits": _trace_rule_hits_for_rows(group_rows),
            })

        all_rows.extend(group_rows)
        seq += len(group_rows)

    msg = (
        "FPA AI 规划完成: 尝试 %d 个三级模块，成功 %d 个，空响应 %d 个，解析失败 %d 个，"
        "AI 生成 %d 行，兜底生成 %d 行，配置跳过 %d 个三级模块，缓存命中 %d 个，后处理 warning %d 个"
    ) % (attempted, success, empty_response, parse_failed, generated, fallback, skipped, cache_hits, warning_count)
    if attempted and success == 0:
        logger.warning(msg)
    else:
        logger.info(msg)
    if cache_path:
        _save_fpa_ai_cache(cache_path, cache)
    _save_fpa_audit_trace(audit_trace_path, {
        "version": 1,
        "profile": profile.name,
        "strategy": strategy,
        "rule_set": rule_set,
        "modules": audit_modules,
    })
    return all_rows


def _write_fpa_rows_md(
    fpa_rows: list[dict[str, object]],
    output_md_path: str,
    ai_filled: bool = False,
    execution_meta: dict[str, str] | None = None,
) -> float:
    _enrich_fpa_rows_with_adjustment(fpa_rows)
    with open(output_md_path, 'w', encoding='utf-8') as f:
        f.write("# FPA 工作量评估\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        if ai_filled:
            f.write(f"**AI 规划**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        if execution_meta:
            for key in ("profile", "strategy", "rule_set"):
                val = execution_meta.get(key, "")
                if val:
                    f.write(f"**{key}**: {val}\n")
        f.write("\n")
        f.write("| 序号 | 子系统(模块) | 资产标识 | 新增/修改功能点 | 类型 | 计算依据归类 | 计算依据说明 | 变更状态 | 调整值 | 要素数量 | 生成方式 | 类型理由 | 源功能过程 | 后处理警告 | 复杂度 | DET | RET | FTR | 复杂度说明 | 调整值计算方式 |\n")
        f.write("|------|-------------|---------|----------------|------|-------------|-------------|---------|-------|---------|---------|---------|-----------|-----------|--------|-----|-----|-----|------------|----------------|\n")
        for row in fpa_rows:
            vals = [
                str(row.get("序号", "")),
                str(row.get("子系统(模块)", "")),
                str(row.get("资产标识", "")),
                str(row.get("新增/修改功能点", "")).replace('|', '\\|'),
                str(row.get("类型", "")),
                str(row.get("计算依据归类", "")),
                str(row.get("计算依据说明", "")).replace("|", chr(92) + "|").replace(chr(10), " "),
                str(row.get("变更状态", "")),
                str(row.get("调整值", "")),
                str(row.get("要素数量", "")),
                str(row.get("生成方式", "")),
                str(row.get("类型理由", "")).replace('|', '\\|'),
                str(row.get("源功能过程", "")).replace('|', '\\|'),
                str(row.get("后处理警告", "")).replace('|', '\\|'),
                str(row.get("复杂度", "")),
                str(row.get("DET", "")),
                str(row.get("RET", "")),
                str(row.get("FTR", "")),
                str(row.get("复杂度说明", "")).replace("|", chr(92) + "|").replace(chr(10), " "),
                str(row.get("调整值计算方式", "")),
            ]
            f.write("| " + " | ".join(vals) + " |\n")
    return calculate_fpa_total(fpa_rows)


def _read_fpa_rows_md_for_audit(fpa_md_path: str) -> tuple[dict[str, str], list[dict[str, object]]]:
    execution_meta: dict[str, str] = {}
    fpa_rows: list[dict[str, object]] = []
    with open(fpa_md_path, encoding="utf-8") as f:
        in_table = False
        for line in f:
            line = line.rstrip()
            meta_match = re.match(r"^\*\*(profile|strategy|rule_set)\*\*:\s*(.*)$", line)
            if meta_match:
                key, value = meta_match.group(1), meta_match.group(2)
                if key in {"profile", "strategy", "rule_set"}:
                    execution_meta[key] = value.strip()
            if "| 序号 | 子系统" in line:
                in_table = True
                continue
            if "|------|" in line and in_table:
                continue
            if in_table:
                cells = parse_md_table_row(line, min_cols=14)
                if cells is not None:
                    fpa_rows.append({
                        "序号": cells[0],
                        "子系统(模块)": cells[1],
                        "资产标识": cells[2],
                        "新增/修改功能点": cells[3],
                        "类型": cells[4],
                        "计算依据归类": cells[5],
                        "计算依据说明": cells[6],
                        "变更状态": cells[7],
                        "调整值": cells[8],
                        "要素数量": cells[9],
                        "生成方式": cells[10],
                        "类型理由": cells[11],
                        "源功能过程": cells[12],
                        "后处理警告": cells[13],
                        "复杂度": cells[14] if len(cells) > 14 else "",
                        "DET": cells[15] if len(cells) > 15 else "",
                        "RET": cells[16] if len(cells) > 16 else "",
                        "FTR": cells[17] if len(cells) > 17 else "",
                        "复杂度说明": cells[18] if len(cells) > 18 else "",
                        "调整值计算方式": cells[19] if len(cells) > 19 else "",
                    })
    return execution_meta, fpa_rows


def _warning_items(text: object) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    return [item.strip() for item in re.split(r"[；;]", raw) if item.strip()]


def _group_rows_for_audit(
    fpa_rows: list[dict[str, object]],
    groups: list[dict[str, object]],
) -> dict[int, list[dict[str, object]]]:
    result: dict[int, list[dict[str, object]]] = {idx: [] for idx in range(1, len(groups) + 1)}
    remaining: list[dict[str, object]] = []
    process_names_by_idx = {
        idx: set(_process_names_for_group(group))
        for idx, group in enumerate(groups, 1)
    }

    def module_markers(group: dict[str, object]) -> list[str]:
        client = str(group.get("client_type", "") or "").strip()
        l1 = str(group.get("l1", "") or "").strip()
        l2 = str(group.get("l2", "") or "").strip()
        l3 = str(group.get("l3", "") or "").strip()
        markers = [
            f"【{client}】{l1}-{l2}-{l3}" if client and l1 and l2 and l3 else "",
            f"{l1}-{l2}-{l3}" if l1 and l2 and l3 else "",
            f"{l2}-{l3}" if l2 and l3 else "",
        ]
        return [marker for marker in markers if marker]

    def choose_by_module_marker(row: dict[str, object], candidate_idxs: list[int]) -> int | None:
        point_name = str(row.get("新增/修改功能点", "") or "")
        explanation = str(row.get("计算依据说明", "") or "")
        haystack = f"{point_name}\n{explanation}"
        matches: list[tuple[int, int]] = []
        for idx in candidate_idxs:
            marker_len = max(
                (len(marker) for marker in module_markers(groups[idx - 1]) if marker in haystack),
                default=0,
            )
            if marker_len:
                matches.append((marker_len, idx))
        if not matches:
            return None
        matches.sort(reverse=True)
        return matches[0][1]

    for row in fpa_rows:
        sources = _source_process_set(row)
        source_matches = [
            idx
            for idx, process_names in process_names_by_idx.items()
            if process_names and sources & process_names
        ]
        if len(source_matches) == 1:
            result[source_matches[0]].append(row)
            continue
        if len(source_matches) > 1:
            idx = choose_by_module_marker(row, source_matches) or source_matches[0]
            result[idx].append(row)
            continue

        marker_matches = [
            idx
            for idx in range(1, len(groups) + 1)
            if choose_by_module_marker(row, [idx]) is not None
        ]
        if marker_matches:
            idx = choose_by_module_marker(row, marker_matches) or marker_matches[0]
            result[idx].append(row)
        else:
            remaining.append(row)

    if remaining and groups:
        result.setdefault(len(groups), []).extend(remaining)
    return result


def _rule_hit_for_audit(row: dict[str, object]) -> tuple[str, str]:
    """根据当前已落表的审计字段还原规则/校验命中说明。"""
    generation = str(row.get("生成方式", "") or "").strip()
    name = str(row.get("新增/修改功能点", "") or "")
    fpa_type = str(row.get("类型", "") or "")
    reason = str(row.get("类型理由", "") or "").strip()
    warning = str(row.get("后处理警告", "") or "").strip()
    text = f"{name} {reason} {warning}"

    if generation == "rules_fallback":
        return "coverage.rules_fallback", reason or "AI 未覆盖功能过程时，按规则集补齐。"
    if "界面开发" in name:
        return "unified_ui.ui_merge", reason or "同一三级模块界面能力默认合并为一条。"
    if "外部系统维护" in text or "外部应用维护" in text or "引用外部" in text:
        return "strict_fpa.external_data_group", reason or "命中外部维护数据组规则。"
    if "本系统维护" in text or "逻辑数据组" in text:
        return "strict_fpa.internal_data_group", reason or "命中内部逻辑数据组规则。"
    if "事务功能" in text:
        return f"strict_fpa.transaction.{fpa_type.lower()}", reason or "命中事务功能类型规则。"
    if "关键词命中" in text:
        return f"unified_ui.keyword.{fpa_type.lower()}", reason or "命中关键词类型兜底规则。"
    if generation in {"ai", "ai_cache"}:
        return "postprocess.ai_type_validation", reason or "AI 输出经类型合法性和业务冲突规则校验后采用。"
    return "profile.fallback", reason or "按当前 profile 兜底规则生成。"


def _rule_hits_from_audit_trace(audit_trace: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    by_seq: dict[str, list[dict[str, object]]] = {}
    modules = audit_trace.get("modules", [])
    if not isinstance(modules, list):
        return by_seq
    for module in modules:
        if not isinstance(module, dict):
            continue
        hits = module.get("rule_hits", [])
        if not isinstance(hits, list):
            continue
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            seq = str(hit.get("fpa_seq", "") or "").strip()
            if seq:
                by_seq.setdefault(seq, []).append(hit)
    return by_seq


def _warning_source_for_row(
    rule_hits_by_seq: dict[str, list[dict[str, object]]],
    row_seq: object,
    warning: str,
) -> tuple[str, str]:
    for hit in rule_hits_by_seq.get(str(row_seq or ""), []):
        hit_warnings = hit.get("warnings", [])
        if isinstance(hit_warnings, list) and any(str(item).strip() == warning for item in hit_warnings):
            return str(hit.get("rule_id", "") or ""), str(hit.get("rule_desc", "") or "")
    return "", ""


FPA_CHECK_DEFAULT_COLUMNS: dict[str, list[str]] = {
    "FPA结果": [
        "序号", "子系统(模块)", "资产标识", "新增/修改功能点", "类型", "计算依据归类",
        "计算依据说明", "变更状态", "调整值", "要素数量", "生成方式", "类型理由",
        "源功能过程", "后处理警告", "复杂度", "DET", "RET", "FTR", "复杂度说明",
        "调整值计算方式", "profile", "strategy", "rule_set",
    ],
    "覆盖审核": [
        "模块序号", "客户端类型", "一级模块", "二级模块", "三级模块",
        "功能过程总数", "已覆盖数", "未覆盖数", "已覆盖功能过程", "未覆盖功能过程",
        "生成方式统计", "Warnings",
    ],
    "Warnings": ["级别", "FPA行序号", "模块序号", "对象", "Warning", "来源规则ID", "来源说明"],
    "规则命中详情": [
        "模块序号", "客户端类型", "一级模块", "二级模块", "三级模块",
        "FPA行序号", "功能点名称", "生成方式", "rule_set",
        "命中对象", "规则ID", "规则说明", "建议类型", "是否采用", "Warnings",
    ],
    "AI原始返回": ["模块", "三级模块", "来源", "Warnings", "AI原始Rows JSON"],
}


def _fpa_check_columns() -> dict[str, list[str]]:
    from ai_gen_reimbursement_docs.config_utils import load_fpa_check_columns

    configured = load_fpa_check_columns()
    columns: dict[str, list[str]] = {}
    for sheet_name, defaults in FPA_CHECK_DEFAULT_COLUMNS.items():
        selected = configured.get(sheet_name, [])
        if selected:
            filtered = [column for column in selected if column in defaults]
            columns[sheet_name] = filtered or list(defaults)
        else:
            columns[sheet_name] = list(defaults)
    return columns


def _append_audit_row(ws, columns: list[str], values: dict[str, object]) -> None:
    ws.append([values.get(column, "") for column in columns])


def _header_index(ws) -> dict[str, int]:
    return {
        str(cell.value): index
        for index, cell in enumerate(ws[1])
        if cell.value is not None
    }


def generate_fpa_check_xlsx_from_md(
    fpa_md_path: str,
    tree_md_path: str,
    output_path: str,
    audit_trace_path: str = "",
) -> str:
    """生成 FPA 审核副本，不影响正式交付 Excel。"""
    logger.info("第1.5步：生成 FPA 审核副本...")
    execution_meta, fpa_rows = _read_fpa_rows_md_for_audit(fpa_md_path)
    tree_rows = parse_module_tree_md(tree_md_path)
    groups = _group_rows_by_l3(tree_rows)
    rows_by_module = _group_rows_for_audit(fpa_rows, groups)
    audit_trace = _load_fpa_audit_trace(audit_trace_path)
    rule_hits_by_seq = _rule_hits_from_audit_trace(audit_trace)
    audit_modules = audit_trace.get("modules", [])
    if not isinstance(audit_modules, list):
        audit_modules = []
    config_warnings_by_module_idx: dict[int, list[str]] = {}
    trace_warnings_by_module_idx: dict[int, list[str]] = {}
    for module_idx, item in enumerate(audit_modules, 1):
        if not isinstance(item, dict):
            continue
        item_warnings = item.get("warnings", [])
        if not isinstance(item_warnings, list):
            continue
        config_warnings = [str(w).strip() for w in item_warnings if _is_config_warning(w)]
        if config_warnings:
            config_warnings_by_module_idx[module_idx] = config_warnings
        trace_warnings = [str(w).strip() for w in item_warnings if str(w).strip() and not _is_config_warning(w)]
        if trace_warnings:
            trace_warnings_by_module_idx[module_idx] = trace_warnings
    raw_audit_by_module_idx: dict[int, dict[str, object]] = {
        module_idx: item
        for module_idx, item in enumerate(audit_modules, 1)
        if isinstance(item, dict)
    }
    warnings_by_module_idx: dict[int, list[str]] = {}
    for idx in range(1, len(groups) + 1):
        module_warnings: list[str] = []
        for row in rows_by_module.get(idx, []):
            module_warnings.extend(_warning_items(row.get("后处理警告", "")))
        module_warnings.extend(config_warnings_by_module_idx.get(idx, []))
        for warning in trace_warnings_by_module_idx.get(idx, []):
            if warning not in module_warnings:
                module_warnings.append(warning)
        warnings_by_module_idx[idx] = module_warnings
    profile = get_fpa_profile(execution_meta.get("profile", "") or "unified_ui")
    audit_reports = _build_fpa_audit_reports_for_groups(
        groups=groups,
        rows_by_module=rows_by_module,
        warnings_by_module=warnings_by_module_idx,
        profile=profile,
        profile_version=profile.version,
        strategy=execution_meta.get("strategy", ""),
        rule_set=execution_meta.get("rule_set", ""),
        raw_audit_by_module=raw_audit_by_module_idx,
        rule_hits_by_seq=rule_hits_by_seq,
    )
    sheet_columns = _fpa_check_columns()

    wb = openpyxl.Workbook()
    ws_result = wb.active
    ws_result.title = "FPA结果"
    ws_result.append(sheet_columns["FPA结果"])
    warning_rows: list[dict[str, object]] = []
    for row in fpa_rows:
        _append_audit_row(ws_result, sheet_columns["FPA结果"], {
            "序号": row.get("序号", ""),
            "子系统(模块)": row.get("子系统(模块)", ""),
            "资产标识": row.get("资产标识", ""),
            "新增/修改功能点": row.get("新增/修改功能点", ""),
            "类型": row.get("类型", ""),
            "计算依据归类": row.get("计算依据归类", ""),
            "计算依据说明": row.get("计算依据说明", ""),
            "变更状态": row.get("变更状态", ""),
            "调整值": row.get("调整值", ""),
            "要素数量": row.get("要素数量", ""),
            "生成方式": row.get("生成方式", ""),
            "类型理由": row.get("类型理由", ""),
            "源功能过程": row.get("源功能过程", ""),
            "后处理警告": row.get("后处理警告", ""),
            "复杂度": row.get("复杂度", ""),
            "DET": row.get("DET", ""),
            "RET": row.get("RET", ""),
            "FTR": row.get("FTR", ""),
            "复杂度说明": row.get("复杂度说明", ""),
            "调整值计算方式": row.get("调整值计算方式", ""),
            "profile": execution_meta.get("profile", ""),
            "strategy": execution_meta.get("strategy", ""),
            "rule_set": execution_meta.get("rule_set", ""),
        })
        for warning in _warning_items(row.get("后处理警告", "")):
            source_rule_id, source_rule_desc = _warning_source_for_row(
                rule_hits_by_seq,
                row.get("序号", ""),
                warning,
            )
            warning_rows.append({
                "级别": "row",
                "FPA行序号": row.get("序号", ""),
                "模块序号": "",
                "对象": row.get("新增/修改功能点", ""),
                "Warning": warning,
                "来源规则ID": source_rule_id,
                "来源说明": source_rule_desc,
            })

    ws_coverage = wb.create_sheet("覆盖审核")
    ws_coverage.append(sheet_columns["覆盖审核"])
    for idx, audit_report in enumerate(audit_reports, 1):
        group = groups[idx - 1]
        module_payload = audit_report.module
        module_warnings = list(warnings_by_module_idx.get(idx, []))
        coverage_warnings: list[str] = []
        if audit_report.missing_processes:
            coverage_warnings.append(f"未覆盖功能过程: {'、'.join(audit_report.missing_processes)}")
            module_warnings.extend(coverage_warnings)
        _append_audit_row(ws_coverage, sheet_columns["覆盖审核"], {
            "模块序号": idx,
            "客户端类型": module_payload.get("client_type", ""),
            "一级模块": module_payload.get("l1", ""),
            "二级模块": module_payload.get("l2", ""),
            "三级模块": module_payload.get("l3", ""),
            "功能过程总数": audit_report.process_total,
            "已覆盖数": len(audit_report.covered_processes),
            "未覆盖数": len(audit_report.missing_processes),
            "已覆盖功能过程": "、".join(audit_report.covered_processes),
            "未覆盖功能过程": "、".join(audit_report.missing_processes),
            "生成方式统计": _json.dumps(audit_report.generation_counts, ensure_ascii=False, sort_keys=True),
            "Warnings": "；".join(module_warnings),
        })
        for warning in coverage_warnings:
            warning_rows.append({
                "级别": "module",
                "FPA行序号": "",
                "模块序号": idx,
                "对象": group.get("l3", ""),
                "Warning": warning,
                "来源规则ID": "coverage.missing_process",
                "来源说明": "功能过程未被任何 FPA 行源功能过程覆盖。",
            })
        for warning in config_warnings_by_module_idx.get(idx, []):
            warning_rows.append({
                "级别": "module",
                "FPA行序号": "",
                "模块序号": idx,
                "对象": group.get("l3", ""),
                "Warning": warning,
                "来源规则ID": "config.external_data_rules.external_service",
                "来源说明": "rule_set.external_data_rules 将普通外部服务配置为外部数据组，配置加载不中断但需要人工复核。",
            })
        for warning in trace_warnings_by_module_idx.get(idx, []):
            if any(item.get("Warning") == warning for item in warning_rows):
                continue
            warning_rows.append({
                "级别": "module",
                "FPA行序号": "",
                "模块序号": idx,
                "对象": group.get("l3", ""),
                "Warning": warning,
                "来源规则ID": "audit.module_warning",
                "来源说明": "生成期模块级审核 warning。",
            })

    ws_warnings = wb.create_sheet("Warnings")
    ws_warnings.append(sheet_columns["Warnings"])
    for item in warning_rows:
        _append_audit_row(ws_warnings, sheet_columns["Warnings"], item)

    ws_rule_hits = wb.create_sheet("规则命中详情")
    ws_rule_hits.append(sheet_columns["规则命中详情"])
    for idx, audit_report in enumerate(audit_reports, 1):
        module_payload = audit_report.module
        for hit in audit_report.rule_hits:
            warnings = "；".join(
                str(x) for x in hit.get("warnings", [])
                if isinstance(hit.get("warnings", []), list) and str(x).strip()
            )
            _append_audit_row(ws_rule_hits, sheet_columns["规则命中详情"], {
                "模块序号": idx,
                "客户端类型": module_payload.get("client_type", ""),
                "一级模块": module_payload.get("l1", ""),
                "二级模块": module_payload.get("l2", ""),
                "三级模块": module_payload.get("l3", ""),
                "FPA行序号": hit.get("fpa_seq", ""),
                "功能点名称": hit.get("function_point", ""),
                "生成方式": hit.get("generation", ""),
                "rule_set": audit_report.rule_set,
                "命中对象": hit.get("hit_object", ""),
                "规则ID": hit.get("rule_id", ""),
                "规则说明": hit.get("rule_desc", ""),
                "建议类型": hit.get("suggested_type", ""),
                "是否采用": hit.get("adopted", ""),
                "Warnings": warnings,
            })

    ws_raw = wb.create_sheet("AI原始返回")
    ws_raw.append(sheet_columns["AI原始返回"])
    for audit_report in audit_reports:
        if not audit_report.raw_source and not audit_report.raw_rows and not audit_report.raw_warnings:
            continue
        _append_audit_row(ws_raw, sheet_columns["AI原始返回"], {
            "模块": _group_tag(audit_report.module),
            "三级模块": audit_report.module.get("l3", ""),
            "来源": audit_report.raw_source,
            "Warnings": "；".join(str(x) for x in audit_report.raw_warnings if str(x).strip()),
            "AI原始Rows JSON": _json.dumps(audit_report.raw_rows, ensure_ascii=False, indent=2),
        })

    header_fill = PatternFill("solid", fgColor="D9EAF7")
    warning_fill = PatternFill("solid", fgColor="FFF2CC")
    missing_fill = PatternFill("solid", fgColor="FCE4D6")

    for ws in (ws_result, ws_coverage, ws_warnings, ws_rule_hits, ws_raw):
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
        for column_cells in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in column_cells)
            ws.column_dimensions[column_cells[0].column_letter].width = min(max(max_len + 2, 10), 48)
        for row in ws.iter_rows():
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="center")
        headers = _header_index(ws)
        if ws.title == "FPA结果":
            warning_idx = headers.get("后处理警告")
            generation_idx = headers.get("生成方式")
            for row in ws.iter_rows(min_row=2):
                warning_value = row[warning_idx].value if warning_idx is not None else ""
                generation_value = row[generation_idx].value if generation_idx is not None else ""
                if str(warning_value or "").strip():
                    for cell in row:
                        cell.fill = warning_fill
                if str(generation_value or "") == "rules_fallback":
                    for cell in row:
                        cell.fill = missing_fill
        if ws.title == "覆盖审核":
            missing_idx = headers.get("未覆盖数")
            for row in ws.iter_rows(min_row=2):
                missing_count = row[missing_idx].value if missing_idx is not None else 0
                try:
                    has_missing = int(missing_count or 0) > 0
                except (TypeError, ValueError):
                    has_missing = False
                if has_missing:
                    for cell in row:
                        cell.fill = missing_fill
        if ws.title == "规则命中详情":
            generation_idx = headers.get("生成方式")
            warning_idx = headers.get("Warnings")
            for row in ws.iter_rows(min_row=2):
                generation_value = row[generation_idx].value if generation_idx is not None else ""
                warning_value = row[warning_idx].value if warning_idx is not None else ""
                if str(warning_value or "").strip():
                    for cell in row:
                        cell.fill = warning_fill
                if str(generation_value or "") == "rules_fallback":
                    for cell in row:
                        cell.fill = missing_fill

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    wb.save(output_path)
    logger.info("FPA 审核副本已生成: %s", output_path)
    return output_path


def init_fpa_template_md(
    tree_md_path: str,
    meta_md_path: str,
    output_md_path: str,
    summary_md_path: str = "",
    profile_name: str = "",
    rule_set: str = "",
) -> str:
    """生成 FPA 模板 MD（规则骨架，F/G 列留空待 AI 填充）。

    Args:
        summary_md_path: 非空时同步写入 gen-fpa-FPA工作量-总和.md（调整值×要素数量 的求和）
    """
    logger.info("第1.1步：生成 FPA 模板 MD...")
    meta = parse_meta_md(meta_md_path)
    rows = parse_module_tree_md(tree_md_path)
    execution = resolve_fpa_execution_config(profile_name, rule_set=rule_set)
    profile = execution.profile
    rule_set_token = set_current_fpa_rule_set_config(execution.rule_set_config)
    try:
        fpa_rows = _build_fpa_rule_rows(rows, meta, profile=profile)
    finally:
        reset_current_fpa_rule_set_config(rule_set_token)

    total = _write_fpa_rows_md(
        fpa_rows,
        output_md_path,
        execution_meta={
            "profile": execution.profile.name,
            "strategy": execution.strategy,
            "rule_set": execution.rule_set,
        },
    )

    logger.info(f"FPA 模板 MD 已生成: {output_md_path} ({len(fpa_rows)} 行)")

    if summary_md_path:
        write_fpa_summary_md(summary_md_path, total)
        logger.info(f"第1.2步：FPA工作量已写入: {summary_md_path} ({total})")

    return output_md_path


def plan_fpa_md_from_tree(
    tree_md_path: str,
    meta_md_path: str,
    output_md_path: str,
    template_path: str = "",
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    summary_md_path: str = "",
    profile_name: str = "",
    strategy: str = "",
    rule_set: str = "",
    audit_trace_path: str = "",
) -> str:
    """以三级模块为单位 AI 规划 FPA 行，并写入 MD。"""
    logger.info("第1.3步：AI 规划 FPA 数据...")
    meta = parse_meta_md(meta_md_path)
    rows = parse_module_tree_md(tree_md_path)
    profile = get_fpa_profile(profile_name)
    execution = resolve_fpa_execution_config(profile.name, strategy, rule_set)
    profile = execution.profile
    judgement_rules = _read_fpa_judgement_rules(template_path)
    if not judgement_rules:
        logger.warning("未配置「计算依据归类判定原则」，AI 输出的归类将无法按模板 index 映射")
    cache_path = os.path.join(os.path.dirname(output_md_path) or ".", "fpa_ai_cache.json") if api_key else ""
    rule_set_token = set_current_fpa_rule_set_config(execution.rule_set_config)
    try:
        fpa_rows = _plan_fpa_rows_with_ai(
            rows,
            meta,
            judgement_rules,
            api_key,
            model,
            base_url,
            cache_path=cache_path,
            profile=profile,
            strategy=execution.strategy,
            rule_set=execution.rule_set,
            rule_set_config=execution.rule_set_config,
            audit_trace_path=audit_trace_path,
        )
    finally:
        reset_current_fpa_rule_set_config(rule_set_token)
    total = _write_fpa_rows_md(
        fpa_rows,
        output_md_path,
        ai_filled=any(str(row.get("生成方式", "")) in {"ai", "ai_cache"} for row in fpa_rows),
        execution_meta={
            "profile": execution.profile.name,
            "strategy": execution.strategy,
            "rule_set": execution.rule_set,
        },
    )
    if summary_md_path:
        write_fpa_summary_md(summary_md_path, total)
        logger.info("第1.2步：FPA工作量已更新: %s (%s)", summary_md_path, total)
    logger.info("FPA 规划 MD 已生成: %s (%d 行)", output_md_path, len(fpa_rows))
    return output_md_path


def _prepare_fpa_preview_md_dir(
    *,
    file_path: str,
    work_dir: str,
    keep_preview_files: bool,
    use_preview_cache: bool,
    temp_prefix: str,
    required_files: list[str],
) -> tuple[str, tempfile.TemporaryDirectory[str] | None, bool]:
    temp_ctx: tempfile.TemporaryDirectory[str] | None = None
    if work_dir:
        md_dir = os.path.join(work_dir, "fpa-preview-md")
        os.makedirs(md_dir, exist_ok=True)
    elif keep_preview_files:
        md_dir = os.path.join(os.path.dirname(os.path.abspath(file_path)), ".fpa-preview", "fpa-preview-md")
        os.makedirs(md_dir, exist_ok=True)
    else:
        temp_ctx = tempfile.TemporaryDirectory(prefix=temp_prefix)
        md_dir = temp_ctx.name

    cache_ready = all(os.path.exists(os.path.join(md_dir, name)) for name in required_files)
    if use_preview_cache and cache_ready:
        return md_dir, temp_ctx, True

    from ai_gen_reimbursement_docs.excel_source import generate_md_files

    generate_md_files(file_path, md_dir)
    return md_dir, temp_ctx, False


def preview_fpa_modules(
    *,
    file_path: str,
    work_dir: str = "",
    use_preview_cache: bool = False,
    keep_preview_files: bool = False,
) -> dict[str, object]:
    """解析功能清单并返回可预览的三级模块列表，不调用 AI，不生成正式交付物。"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"功能清单输入文件不存在: {file_path}")
    if not work_dir and not keep_preview_files and not use_preview_cache:
        base_data = read_base_data_from_excel(file_path)
        rows = base_data["tree_rows"]
        groups = _group_rows_by_l3(rows if isinstance(rows, list) else [])
        modules: list[dict[str, object]] = []
        for idx, group in enumerate(groups, 1):
            processes = group.get("processes", [])
            process_count = len(processes) if isinstance(processes, list) else 0
            path_parts = [
                str(group.get("client_type", "") or "").strip(),
                str(group.get("l1", "") or "").strip(),
                str(group.get("l2", "") or "").strip(),
                str(group.get("l3", "") or "").strip(),
            ]
            label_path = " / ".join([part for part in path_parts if part])
            modules.append({
                "index": idx,
                "client_type": group.get("client_type", ""),
                "l1": group.get("l1", ""),
                "l2": group.get("l2", ""),
                "l3": group.get("l3", ""),
                "l3_desc": group.get("l3_desc", ""),
                "process_count": process_count,
                "label": f"{idx}. {label_path}" if label_path else str(idx),
            })
        return {
            "modules": modules,
            "warnings": [] if modules else ["未解析到三级模块"],
            "preview_md_dir": "",
            "preview_cache_used": False,
        }
    md_dir, temp_ctx, cache_used = _prepare_fpa_preview_md_dir(
        file_path=file_path,
        work_dir=work_dir,
        keep_preview_files=keep_preview_files,
        use_preview_cache=use_preview_cache,
        temp_prefix="ard-fpa-preview-modules-",
        required_files=["0.1.gen-basedata-功能清单-模块树.md"],
    )
    try:
        tree_md = os.path.join(md_dir, "0.1.gen-basedata-功能清单-模块树.md")
        rows = parse_module_tree_md(tree_md)
        modules: list[dict[str, object]] = []
        for idx, group in enumerate(_group_rows_by_l3(rows), 1):
            processes = group.get("processes", [])
            process_count = len(processes) if isinstance(processes, list) else 0
            path_parts = [
                str(group.get("client_type", "") or "").strip(),
                str(group.get("l1", "") or "").strip(),
                str(group.get("l2", "") or "").strip(),
                str(group.get("l3", "") or "").strip(),
            ]
            label_path = " / ".join([part for part in path_parts if part])
            modules.append({
                "index": idx,
                "client_type": group.get("client_type", ""),
                "l1": group.get("l1", ""),
                "l2": group.get("l2", ""),
                "l3": group.get("l3", ""),
                "l3_desc": group.get("l3_desc", ""),
                "process_count": process_count,
                "label": f"{idx}. {label_path}" if label_path else str(idx),
            })
        return {
            "modules": modules,
            "warnings": [] if modules else ["未解析到三级模块"],
            "preview_md_dir": md_dir,
            "preview_cache_used": cache_used,
        }
    finally:
        if temp_ctx is not None:
            temp_ctx.cleanup()


def preview_fpa_module(
    *,
    file_path: str,
    module_name: str = "",
    module_index: int | None = None,
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    template_path: str = "",
    work_dir: str = "",
    profile_name: str = "",
    strategy: str = "",
    rule_set: str = "",
    use_preview_cache: bool = False,
    keep_preview_files: bool = False,
) -> dict[str, object]:
    """预览单个三级模块的 FPA 规划结果，不生成正式 Excel。"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"功能清单输入文件不存在: {file_path}")
    execution = resolve_fpa_execution_config(profile_name, strategy, rule_set)
    profile = execution.profile
    temp_ctx = None
    cache_used = False
    md_dir = ""
    try:
        if not work_dir and not keep_preview_files and not use_preview_cache:
            base_data = read_base_data_from_excel(file_path)
            rows = base_data["tree_rows"] if isinstance(base_data["tree_rows"], list) else []
            meta = base_data["meta"] if isinstance(base_data["meta"], dict) else {}
        else:
            md_dir, temp_ctx, cache_used = _prepare_fpa_preview_md_dir(
                file_path=file_path,
                work_dir=work_dir,
                keep_preview_files=keep_preview_files,
                use_preview_cache=use_preview_cache,
                temp_prefix="ard-fpa-preview-",
                required_files=[
                    "0.1.gen-basedata-功能清单-模块树.md",
                    "0.2.gen-basedata-录入文档元数据-模板.md",
                ],
            )
            tree_md = os.path.join(md_dir, "0.1.gen-basedata-功能清单-模块树.md")
            meta_md = os.path.join(md_dir, "0.2.gen-basedata-录入文档元数据-模板.md")
            rows = parse_module_tree_md(tree_md)
            meta = parse_meta_md(meta_md) if os.path.exists(meta_md) else {}
        groups = _group_rows_by_l3(rows)

        matches: list[tuple[int, dict[str, object]]] = []
        for idx, group in enumerate(groups, 1):
            if module_index is not None and idx == module_index:
                matches.append((idx, group))
            elif module_index is None and module_name and str(group.get("l3", "")) == module_name:
                matches.append((idx, group))
        if module_index is None and not module_name:
            raise ValueError("请指定 module_name 或 module_index")
        if not matches:
            raise ValueError(f"未找到三级模块: {module_name or module_index}")
        if module_index is None and len(matches) > 1:
            indexes = [idx for idx, _ in matches]
            raise ValueError(f"存在多个同名三级模块「{module_name}」，请用 module_index 指定: {indexes}")

        idx, group = matches[0]
        judgement_rules = _read_fpa_judgement_rules(template_path)
        warnings: list[str] = []
        used_ai = execution.strategy in {"ai_first", "ai_only"}
        debug: dict[str, object] = {
            "ai_called": False,
            "reason": execution.strategy,
            "model": model,
            "system_prompt": "",
            "system_prompt_source": "未配置",
            "user_prompt": "",
            "user_prompt_source": "未配置",
            "core_rules_source": "未配置",
            "ai_prompt": "",
            "raw_response": "",
            "thinking": "",
            "parsed_rows": [],
            "final_rows": [],
        }
        rule_set_token = set_current_fpa_rule_set_config(execution.rule_set_config)
        try:
            if execution.strategy in {"rules_first", "rules_only"}:
                used_ai = False
                debug["reason"] = execution.strategy
                fpa_rows = profile.fallback_rows_for_l3(group, meta, start_seq=1)
                _attach_profile_rule_hits(fpa_rows, profile=profile, generation="fallback")
                if execution.strategy == "rules_first":
                    rules_first_reasons = _rules_first_ai_reasons(group, fpa_rows)
                    if rules_first_reasons and api_key:
                        debug["reason"] = "rules_first_needs_ai"
                        raw_rows, debug = _ai_plan_fpa_rows_for_l3_debug(
                            group, judgement_rules, _build_domain_context(meta), api_key, model, base_url,
                            profile=profile,
                        )
                        debug["reason"] = "rules_first_needs_ai"
                        fpa_rows, warnings = _normalize_ai_fpa_rows_for_l3(
                            group=group,
                            meta=meta,
                            ai_rows=raw_rows,
                            judgement_rules=judgement_rules,
                            start_seq=1,
                            profile=profile,
                            strategy=execution.strategy,
                        )
                        fpa_rows, supplement_warnings = _supplement_ai_rows_with_rules(
                            group=group,
                            meta=meta,
                            ai_rows=fpa_rows,
                            profile=profile,
                            strategy=execution.strategy,
                            rule_set_config=execution.rule_set_config,
                        )
                        warnings.extend(supplement_warnings)
                        _, validation_warnings = _validate_fpa_rows_for_l3(
                            group=group,
                            rows=fpa_rows,
                        )
                        warnings.extend(validation_warnings)
                        warnings.insert(0, "规则结果触发 AI 复核: " + "；".join(rules_first_reasons))
                        if not fpa_rows:
                            raise ValueError("AI 规划未生成有效 FPA 行")
                        used_ai = True
                    elif rules_first_reasons:
                        warning = "规则结果需要 AI 复核但未配置 API Key，已保留规则生成结果: " + "；".join(rules_first_reasons)
                        warnings.append(warning)
                        debug["reason"] = "rules_first_needs_ai_missing_api_key"
                    else:
                        debug["reason"] = "rules_first_rules_ok"
            elif not api_key:
                debug["reason"] = "missing_api_key"
                raise ValueError(f"FPA strategy={execution.strategy} 需要 API Key，当前未配置")
            else:
                raw_rows, debug = _ai_plan_fpa_rows_for_l3_debug(
                    group, judgement_rules, _build_domain_context(meta), api_key, model, base_url,
                    profile=profile,
                )
                fpa_rows, warnings = _normalize_ai_fpa_rows_for_l3(
                    group=group,
                    meta=meta,
                    ai_rows=raw_rows,
                    judgement_rules=judgement_rules,
                    start_seq=1,
                    profile=profile,
                    strategy=execution.strategy,
                )
                fpa_rows, supplement_warnings = _supplement_ai_rows_with_rules(
                    group=group,
                    meta=meta,
                    ai_rows=fpa_rows,
                    profile=profile,
                    strategy=execution.strategy,
                    rule_set_config=execution.rule_set_config,
                )
                warnings.extend(supplement_warnings)
                _, validation_warnings = _validate_fpa_rows_for_l3(
                    group=group,
                    rows=fpa_rows,
                )
                warnings.extend(validation_warnings)
                if not fpa_rows:
                    raise ValueError("AI 规划未生成有效 FPA 行")
        except Exception as exc:
            from ai_gen_reimbursement_docs.config_utils import FpaPromptConfigError

            if isinstance(exc, FpaAiDebugError):
                debug = exc.debug
            debug["error"] = str(exc)
            if isinstance(exc, FpaPromptConfigError):
                raise
            if execution.strategy == "ai_only" or not api_key:
                raise
            used_ai = False
            debug["reason"] = "ai_failed_fallback"
            warnings.append(f"AI 调用或解析失败，已使用兜底生成: {exc}")
            logger.warning("FPA 预览 AI 失败 [%s]: %s", _group_tag(group), exc)
            fpa_rows = profile.fallback_rows_for_l3(group, meta, start_seq=1)
        finally:
            reset_current_fpa_rule_set_config(rule_set_token)
        warnings = _with_config_warnings(warnings, execution.rule_set_config)

        def _row_to_preview(row: dict[str, object]) -> dict[str, object]:
            basis = str(row.get("计算依据归类", ""))
            basis_index = judgement_rules.index(basis) + 1 if basis in judgement_rules else None
            return {
                "name": row.get("新增/修改功能点", ""),
                "type": row.get("类型", ""),
                "type_reason": row.get("类型理由", ""),
                "classification_basis": basis,
                "classification_basis_index": basis_index,
                "explanation": _format_fpa_explanation(str(row.get("计算依据说明", "") or "")),
                "source_processes": [
                    x for x in str(row.get("源功能过程", "")).split("、") if x
                ],
                "source_process_ids": sorted(_source_process_ids_from_row(row)),
                "generation": row.get("生成方式", "ai" if used_ai else "fallback"),
            }

        preview_rows = [_row_to_preview(row) for row in fpa_rows]
        debug["final_rows"] = preview_rows
        raw_source = "ai" if debug.get("ai_called") and used_ai else "rules"
        if debug.get("reason") == "ai_failed_fallback":
            raw_source = "rules_fallback"
        raw_rows = debug.get("parsed_rows", [])
        audit = _build_fpa_audit_reports_for_groups(
            groups=[group],
            rows_by_module={1: fpa_rows},
            warnings_by_module={1: warnings},
            profile=profile,
            profile_version=profile.version,
            strategy=execution.strategy,
            rule_set=execution.rule_set,
            raw_audit_by_module={
                1: {
                    "source": raw_source,
                    "raw_rows": raw_rows if isinstance(raw_rows, list) else [],
                    "warnings": warnings,
                }
            },
        )[0]
        audit.module["index"] = idx
        module_payload = dict(audit.module)
        return {
            "module": module_payload,
            "rows": preview_rows,
            "warnings": warnings,
            "used_ai": used_ai,
            "profile": profile.name,
            "profile_version": profile.version,
            "strategy": execution.strategy,
            "rule_set": execution.rule_set,
            "audit": audit.to_dict(),
            "preview_md_dir": md_dir,
            "preview_cache_used": cache_used,
            "debug": debug,
        }
    finally:
        if temp_ctx is not None:
            temp_ctx.cleanup()


def _format_fpa_explanation(text: str) -> str:
    """格式化 FPA 计算依据说明：加换行排版，不改变原文内容。"""
    NL = chr(10)
    text = text.lstrip("：: ")
    text = text.replace("具体如下", "具体如下" + NL + NL)
    text = text.replace("事件流：", NL + "事件流：")
    text = text.replace("触发事件：", NL + "触发事件：")
    text = text.replace("；", "；" + NL)
    text = text.replace("业务规则", NL + "业务规则")
    text = text.replace("业务数据", NL + "业务数据")
    text = text.replace("涉及表", NL + "涉及表")
    text = text.replace("涉及服务", NL + "涉及服务")
    text = text.replace("；涉及接口", "；" + NL + "涉及接口")
    text = re.sub(re.compile(r"(?<=\S)\s+(?=\d+\.)"), NL, text)
    text = re.sub(re.compile(r"^[	 ]+", re.MULTILINE), "", text)
    text = re.sub(re.compile(r'\n[：:;；]\s*\n'), '\n', text)
    text = re.sub(re.compile(NL + "{3,}"), NL + NL, text)
    return text


def generate_fpa_xlsx_from_md(
    fpa_md_path: str,
    meta_md_path: str,
    template_path: str,
    output_path: str,
) -> str:
    """从已填充的 FPA MD 生成 FPA工作量评估.xlsx。"""
    logger.info("第1.4步：从 FPA MD 生成 Excel...")

    meta = parse_meta_md(meta_md_path)
    base_formula = meta.get("基准值公式", "")
    workload_formula = meta.get("FPA工作量公式", "J{row}*K{row}")

    fpa_rows = []
    with open(fpa_md_path, encoding='utf-8') as f:
        in_table = False
        for line in f:
            line = line.rstrip()
            if "| 序号 | 子系统" in line:
                in_table = True
                continue
            if "|------|" in line and in_table:
                continue
            if in_table:
                cells = parse_md_table_row(line, min_cols=14)
                if cells is not None:
                    fpa_rows.append({
                        "序号": cells[0],
                        "子系统(模块)": cells[1],
                        "资产标识": cells[2],
                        "新增/修改功能点": cells[3],
                        "类型": cells[4],
                        "计算依据归类": cells[5],
                        "计算依据说明": cells[6],
                        "变更状态": cells[7],
                        "调整值": cells[8],
                        "要素数量": cells[9],
                    })

    wb = safe_load_workbook(template_path, 'FPA工作量评估')
    from ai_gen_reimbursement_docs.config_utils import _get_system_config_value
    _fpa_sheet = _get_system_config_value('fpa_sheet', 'FPA功能点估算')
    ws = wb[_fpa_sheet]

    tmpl_format = {}
    for col_idx in range(1, FPA_TOTAL_COLS):
        c = ws.cell(3, col_idx)
        tmpl_format[col_idx] = {
            'font': copy(c.font) if c.font else None,
            'fill': copy(c.fill) if c.fill else None,
            'border': copy(c.border) if c.border else None,
            'number_format': c.number_format,
            'alignment': copy(c.alignment) if c.alignment else None,
        }
    for col_idx in (FPA_COL_FORMULA_BASE, FPA_COL_FORMULA_WORKLOAD):
        c = ws.cell(2, col_idx)
        if c.fill:
            tmpl_format[col_idx]['fill'] = copy(c.fill)

    if ws.max_row >= 3:
        ws.delete_rows(3, ws.max_row - 2)

    for i, fpa_row in enumerate(fpa_rows):
        excel_row = i + 3
        for col_idx, key in FPA_COL_KEY_MAP.items():
            val = fpa_row.get(key, "")
            cell = ws.cell(excel_row, col_idx)
            if col_idx in (FPA_COL_SEQ, FPA_COL_ADJUST, FPA_COL_ELEMENTS):
                try:
                    cell.value = int(val)
                except (ValueError, TypeError):
                    cell.value = val
            elif col_idx == FPA_COL_EXPLANATION:
                cell.value = _format_fpa_explanation(val)
            else:
                cell.value = val
        if base_formula:
            formula = base_formula.replace("E3", f"E{excel_row}") \
                .replace("H3", f"H{excel_row}").replace("I3", f"I{excel_row}") \
                .replace("J3", f"J{excel_row}").replace("K3", f"K{excel_row}")
            ws.cell(excel_row, FPA_COL_FORMULA_BASE).value = f"={formula}" if not formula.startswith('=') else formula
        if workload_formula:
            formula = workload_formula.replace("J{row}", f"J{excel_row}") \
                .replace("K{row}", f"K{excel_row}") \
                .replace("J3", f"J{excel_row}").replace("K3", f"K{excel_row}")
            ws.cell(excel_row, FPA_COL_FORMULA_WORKLOAD).value = f"={formula}" if not formula.startswith('=') else formula
        ws.cell(excel_row, FPA_TOTAL_COLS - 1, "")
        ws.cell(excel_row, FPA_TOTAL_COLS, "")

        for col_idx in range(1, FPA_TOTAL_COLS):
            c = ws.cell(excel_row, col_idx)
            fmt = tmpl_format.get(col_idx, {})
            if fmt.get('font'):
                c.font = fmt['font']
            if fmt.get('border'):
                c.border = fmt['border']
            if fmt.get('number_format'):
                c.number_format = fmt['number_format']
            if col_idx in (9, 12) and fmt.get('fill'):
                c.fill = fmt['fill']
            if col_idx in (FPA_COL_FUNC_POINT, FPA_COL_EXPLANATION):
                orig_align = fmt.get('alignment')
                h = 'left' if col_idx == 7 else (orig_align.horizontal or 'center')
                if orig_align:
                    c.alignment = Alignment(
                        wrap_text=True,
                        vertical='center',
                        horizontal=h,
                    )
                else:
                    c.alignment = Alignment(wrap_text=True, vertical='center', horizontal=h)
            else:
                if fmt.get('alignment'):
                    c.alignment = fmt['alignment']

    last_data_row = len(fpa_rows) + 2
    for col_idx in [FPA_COL_FORMULA_BASE, FPA_COL_ADJUST, FPA_COL_ELEMENTS, FPA_COL_FORMULA_WORKLOAD, FPA_TOTAL_COLS - 1]:
        cell = ws.cell(1, col_idx)
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        cell.value = f"=SUM({col_letter}3:{col_letter}{last_data_row})"
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    try:
        wb.save(output_path)
    except PermissionError:
        temp_path = output_path.rsplit('.', 1)[0] + '_TEMP.xlsx'
        wb.save(temp_path)
        logger.warning(
            "文件被占用，已保存到临时文件: %s\n"
            "关闭 Excel/WPS 后，将 _TEMP 文件重命名替换原文件即可", temp_path
        )
        return temp_path
    logger.info(f"FPA工作量评估已生成: {output_path} ({len(fpa_rows)} 行)")

    return output_path
