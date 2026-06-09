"""FPA 规划口径策略。

每套 profile 自己提供兜底拆分、类型推断和冲突判断，
避免把多套口径分支散落到 gen_fpa.py 主流程中。
"""

from contextvars import ContextVar
from dataclasses import dataclass, field
import re
from string import Template


VALID_FPA_STRATEGIES = {"rules_first", "ai_first", "rules_only", "ai_only"}
VALID_FPA_TYPES = {"EI", "EQ", "EO", "ILF", "EIF"}
VALID_TRANSACTION_FPA_TYPES = {"EI", "EQ", "EO"}
VALID_RULE_MERGE_MODES = {"append", "replace"}

UNIFIED_UI_CORE_RULES = "请在 fpa_config.yaml 的 core_rules.unified_ui_cr 配置 unified_ui 核心口径。"
STRICT_FPA_CORE_RULES = "请在 fpa_config.yaml 的 core_rules.strict_fpa_cr 配置 strict_fpa 核心口径。"
UI_API_MAPPING_CORE_RULES = "请在 fpa_config.yaml 的 core_rules.ui_api_mapping_cr 配置 ui_api_mapping 核心口径。"


EXTERNAL_DATA_GROUP_NOUNS = [
    "数据组", "主数据", "基础数据", "档案", "信息", "记录", "账号", "账户", "单据", "客户",
    "人员", "组织", "机构",
]

EXTERNAL_MAINTAINED_HINTS = [
    "外部应用维护", "外部系统维护", "第三方系统维护", "外部维护", "外部应用提供",
    "外部系统提供", "第三方系统提供", "本系统不维护", "引用外部数据组",
]
EXTERNAL_DATA_NEGATION_HINTS = [
    "不作为外部维护数据组", "不是外部维护数据组", "不按外部维护数据组",
    "不作为外部数据组", "不是外部数据组", "不按外部数据组",
]

EXTERNAL_SERVICE_CALL_HINTS = ("外部接口", "外部服务", "调用", "平台发送", "网关", "服务上传")
ORDINARY_EXTERNAL_SERVICE_ALIASES = (
    "短信平台", "短信服务", "短信网关",
    "支付网关", "支付平台",
    "OCR", "OCR服务", "OCR平台",
    "文件存储", "对象存储", "存储服务",
    "地图服务", "地图平台",
)


@dataclass(frozen=True)
class ExternalDataGroupRule:
    """外部系统维护、本系统只引用的数据组识别规则。"""

    source_aliases: tuple[str, ...]
    data_name: str
    data_nouns: tuple[str, ...] = tuple(EXTERNAL_DATA_GROUP_NOUNS)

    def matches(self, text: str) -> bool:
        return any(alias in text for alias in self.source_aliases) and any(noun in text for noun in self.data_nouns)


@dataclass(frozen=True)
class KeywordTypeRule:
    """按关键词配置事务功能类型兜底规则。"""

    fpa_type: str
    keywords: tuple[str, ...]
    reason: str = ""

    def matches(self, text: str) -> bool:
        return any(keyword in text for keyword in self.keywords)


@dataclass(frozen=True)
class TypeMappingRule:
    """按关键词配置任意 FPA 类型映射规则。"""

    fpa_type: str
    keywords: tuple[str, ...]
    reason: str = ""

    def matches(self, text: str) -> bool:
        return any(keyword in text for keyword in self.keywords)


@dataclass(frozen=True)
class AiTypeConflictRule:
    """按关键词配置 AI type 与规则建议 type 的冲突处理。"""

    expected_type: str
    ai_type: str
    keywords: tuple[str, ...]
    conflict: bool = True
    reason: str = ""

    def matches(self, text: str, expected_type: str, ai_type: str) -> bool:
        return (
            self.expected_type == expected_type
            and self.ai_type == ai_type.upper()
            and any(keyword in text for keyword in self.keywords)
        )


@dataclass(frozen=True)
class InternalDataGroupRule:
    """本系统维护的 ILF 数据组识别规则。"""

    keywords: tuple[str, ...]
    data_name: str
    reason: str = ""

    def matches(self, text: str) -> bool:
        return any(keyword in text for keyword in self.keywords)


@dataclass(frozen=True)
class FpaExecutionConfig:
    """一次 FPA 执行使用的 profile、策略和规则集。"""

    profile: "CustomRulesProfile"
    strategy: str
    rule_set: str
    rule_set_config: "FpaRuleSetConfig"


@dataclass(frozen=True)
class FpaCoverageRules:
    """功能过程覆盖与规则补齐策略。"""

    require_process_coverage: bool | None = None
    require_data_function: bool | None = None


@dataclass(frozen=True)
class FpaUiRowPlanningRule:
    """三级模块界面兜底行生成策略。"""

    enabled: bool | None = None
    scope: str = ""
    merge: str = ""
    name_suffix: str = ""
    fpa_type: str = ""
    reason: str = ""
    empty_process_text: str = ""
    explanation_template: str = ""


@dataclass(frozen=True)
class FpaProcessRowsPlanningRule:
    """功能过程兜底行生成策略。"""

    enabled: bool | None = None
    one_row_per_process: bool | None = None
    default_name_suffix: str = ""
    type_suffixes: dict[str, str] = field(default_factory=dict)
    explanation_template: str = ""


@dataclass(frozen=True)
class FpaRowPlanningRules:
    """一套 rule_set 中的兜底行规划规则。"""

    ui_row: FpaUiRowPlanningRule | None = None
    process_rows: FpaProcessRowsPlanningRule | None = None


@dataclass(frozen=True)
class FpaRuleSetConfig:
    """一套可配置 FPA 规则集。"""

    name: str
    extends: str = ""
    external_data_rules: tuple[ExternalDataGroupRule, ...] = field(default_factory=tuple)
    external_data_rules_merge: str = "append"
    keyword_rules: tuple[KeywordTypeRule, ...] = field(default_factory=tuple)
    keyword_rules_merge: str = "append"
    type_mapping_rules: tuple[TypeMappingRule, ...] = field(default_factory=tuple)
    type_mapping_rules_merge: str = "append"
    ai_type_conflict_rules: tuple[AiTypeConflictRule, ...] = field(default_factory=tuple)
    ai_type_conflict_rules_merge: str = "append"
    internal_data_rules: tuple[InternalDataGroupRule, ...] = field(default_factory=tuple)
    internal_data_rules_merge: str = "append"
    coverage_rules: FpaCoverageRules = field(default_factory=FpaCoverageRules)
    row_planning_rules: FpaRowPlanningRules = field(default_factory=FpaRowPlanningRules)
    config_warnings: tuple[str, ...] = field(default_factory=tuple)
    raw: dict[str, object] = field(default_factory=dict)


_CURRENT_RULE_SET_CONFIG: ContextVar[FpaRuleSetConfig | None] = ContextVar(
    "fpa_rule_set_config",
    default=None,
)

COMPLEXITY_ALIASES = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "低": "low",
    "中": "medium",
    "高": "high",
}
COMPLEXITY_LABELS = {"low": "低", "medium": "中", "high": "高"}


def _normalize_complexity(value: object) -> str:
    text = str(value or "").strip().lower()
    return COMPLEXITY_ALIASES.get(text, "")


def _as_optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _fmt_number(value: int | None) -> str:
    return "" if value is None else str(value)


def _match_complexity_matrix(
    matrix: object,
    *,
    det_count: int,
    secondary_count: int,
) -> str:
    if not isinstance(matrix, list):
        return ""
    for rule in matrix:
        if not isinstance(rule, dict):
            continue
        det_min = _as_optional_int(rule.get("det_min"))
        det_max = _as_optional_int(rule.get("det_max"))
        secondary_min = _as_optional_int(rule.get("ret_min"))
        secondary_max = _as_optional_int(rule.get("ret_max"))
        if secondary_min is None:
            secondary_min = _as_optional_int(rule.get("ftr_min"))
        if secondary_max is None:
            secondary_max = _as_optional_int(rule.get("ftr_max"))
        if det_min is None or secondary_min is None:
            continue
        if det_count < det_min or (det_max is not None and det_count > det_max):
            continue
        if secondary_count < secondary_min or (secondary_max is not None and secondary_count > secondary_max):
            continue
        return _normalize_complexity(rule.get("complexity"))
    return ""


def calculate_fpa_adjustment_for_row(row: dict[str, object]) -> dict[str, object]:
    """Calculate adjustment value and audit fields from configured FPA method."""
    from ai_gen_reimbursement_docs.config_utils import FpaConfigError, load_fpa_adjustment_value_config

    config = load_fpa_adjustment_value_config()
    method = str(config.get("method") or "").strip()
    methods = config.get("methods", {})
    if not isinstance(methods, dict) or method not in methods:
        raise FpaConfigError(f"FPA 配置无效：adjustment_value_methods.{method}")

    fpa_type = str(row.get("类型", "") or row.get("type", "") or "").strip().upper()
    if fpa_type not in VALID_FPA_TYPES:
        raise FpaConfigError(f"FPA 类型非法，无法计算调整值: {fpa_type}")

    if method == "legacy_workload":
        legacy = methods.get("legacy_workload")
        type_weights = legacy.get("type_weights") if isinstance(legacy, dict) else {}
        value = type_weights[fpa_type] if isinstance(type_weights, dict) and fpa_type in type_weights else type_weights["default"]
        return {
            "adjustment_value": int(value) if isinstance(value, float) and value.is_integer() else value,
            "method": method,
            "complexity": "",
            "det_count": row.get("DET", row.get("det_count", "")) or "",
            "ret_count": row.get("RET", row.get("ret_count", "")) or "",
            "ftr_count": row.get("FTR", row.get("ftr_count", "")) or "",
            "complexity_reason": str(row.get("复杂度说明", row.get("complexity_reason", "")) or ""),
        }

    standard = methods.get("standard_fpa")
    if not isinstance(standard, dict):
        raise FpaConfigError("FPA 配置无效：adjustment_value_methods.standard_fpa")
    det_count = _as_optional_int(row.get("DET", row.get("det_count")))
    ret_count = _as_optional_int(row.get("RET", row.get("ret_count")))
    ftr_count = _as_optional_int(row.get("FTR", row.get("ftr_count")))
    ai_complexity = _normalize_complexity(row.get("复杂度", row.get("complexity")))
    final_complexity = ""
    code_reason = ""

    if fpa_type in {"ILF", "EIF"} and det_count is not None and ret_count is not None:
        final_complexity = _match_complexity_matrix(
            standard.get("data_function_complexity_matrix"),
            det_count=det_count,
            secondary_count=ret_count,
        )
        if final_complexity:
            code_reason = (
                f"代码按配置矩阵复算：类型={fpa_type}，DET={det_count}，RET={ret_count}，"
                f"复杂度={COMPLEXITY_LABELS[final_complexity]}。"
            )
    elif fpa_type in {"EI", "EO", "EQ"} and det_count is not None and ftr_count is not None:
        matrices = standard.get("transaction_complexity_matrices")
        matrix = matrices.get(fpa_type) if isinstance(matrices, dict) else None
        final_complexity = _match_complexity_matrix(matrix, det_count=det_count, secondary_count=ftr_count)
        if final_complexity:
            code_reason = (
                f"代码按配置矩阵复算：类型={fpa_type}，DET={det_count}，FTR={ftr_count}，"
                f"复杂度={COMPLEXITY_LABELS[final_complexity]}。"
            )

    if not final_complexity and ai_complexity:
        final_complexity = ai_complexity
        missing = "RET" if fpa_type in {"ILF", "EIF"} else "FTR"
        code_reason = (
            f"DET/{missing} 证据不完整或未命中配置矩阵，采用 AI 输出复杂度="
            f"{COMPLEXITY_LABELS[final_complexity]}。"
        )

    if not final_complexity:
        final_complexity = _normalize_complexity(standard.get("fallback_complexity")) or "low"
        code_reason = f"复杂度证据缺失，采用配置兜底复杂度={COMPLEXITY_LABELS[final_complexity]}。"

    weights = standard.get("weights")
    type_weights = weights.get(fpa_type) if isinstance(weights, dict) else None
    if not isinstance(type_weights, dict) or final_complexity not in type_weights:
        raise FpaConfigError(
            f"FPA 配置无效：adjustment_value_methods.standard_fpa.weights.{fpa_type}.{final_complexity}"
        )
    value = type_weights[final_complexity]
    if isinstance(value, float) and value.is_integer():
        value = int(value)

    ai_reason = str(row.get("复杂度说明", row.get("complexity_reason", "")) or "").strip()
    full_reason = "；".join(part for part in (ai_reason, code_reason) if part)
    return {
        "adjustment_value": value,
        "method": method,
        "complexity": COMPLEXITY_LABELS[final_complexity],
        "det_count": _fmt_number(det_count),
        "ret_count": _fmt_number(ret_count) if fpa_type in {"ILF", "EIF"} else "",
        "ftr_count": _fmt_number(ftr_count) if fpa_type in {"EI", "EO", "EQ"} else "",
        "complexity_reason": full_reason,
    }


def group_tag(group: dict[str, object]) -> str:
    return (
        f"【{group.get('client_type', '')}】"
        f"{group.get('l1', '')}-{group.get('l2', '')}-{group.get('l3', '')}"
    )


def function_point_tag(group: dict[str, object], name: str) -> str:
    base = group_tag(group)
    clean_name = str(name or "").strip()
    if not clean_name:
        return base
    if clean_name.startswith(f"{base}-") or clean_name == base:
        return clean_name
    return f"{base}-{clean_name}"


def adjust_value_for_type(fpa_type: str) -> int | float:
    return calculate_fpa_adjustment_for_row({"类型": fpa_type})["adjustment_value"]


def module_change_status(processes: list[object]) -> str:
    statuses = [
        str(p.get("type", "")).strip()
        for p in processes
        if isinstance(p, dict) and str(p.get("type", "")).strip()
    ]
    if not statuses:
        return ""
    if "新增" in statuses:
        return "新增"
    return statuses[0]


EXPLANATION_REQUIRED_LABELS = ("来源场景：", "业务数据：", "业务规则：", "计算说明：")


def _structure_fallback_explanations(group: dict[str, object], rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Ensure deterministic fallback rows have the review-page explanation shape."""
    for row in rows:
        if str(row.get("生成方式", "") or "") != "fallback":
            continue
        explanation = str(row.get("计算依据说明", "") or "").strip()
        if all(label in explanation for label in EXPLANATION_REQUIRED_LABELS):
            continue
        row["计算依据说明"] = _structured_fallback_explanation(group, row, explanation)
    return rows


def _structured_fallback_explanation(
    group: dict[str, object],
    row: dict[str, object],
    original_explanation: str,
) -> str:
    point_name = str(row.get("新增/修改功能点", "") or group_tag(group))
    fpa_type = str(row.get("类型", "") or "").strip().upper() or "FPA"
    source_processes = str(row.get("源功能过程", "") or "").strip()
    type_reason = str(row.get("类型理由", "") or "").strip()
    business_data = _fallback_business_data(point_name, fpa_type, source_processes)
    business_rule_parts = [
        part for part in [
            source_processes and f"来源功能过程：{source_processes}",
            original_explanation,
            type_reason,
        ]
        if part
    ]
    return "\n".join([
        f"来源场景：来自“{point_name}”。",
        f"业务数据：{business_data}",
        f"业务规则：{'；'.join(business_rule_parts) or '按当前模块功能清单和规则兜底生成。'}",
        f"计算说明：该功能点由规则兜底生成，可支撑 FPA 功能点计量，并按 {fpa_type} 识别。",
    ])


def _fallback_business_data(point_name: str, fpa_type: str, source_processes: str) -> str:
    text = source_processes or point_name
    clean = re.sub(r"^【[^】]+】", "", point_name)
    clean = clean.rsplit("-", 1)[-1] if "-" in clean else clean
    clean = re.sub(r"(数据组|维护|查询|输出|导出|报表|界面开发|接口开发)$", "", clean).strip()
    subject = clean or text or "业务数据"
    if fpa_type in {"ILF", "EIF"}:
        return f"涉及{subject}逻辑数据组。"
    if fpa_type == "EQ":
        return f"读取并展示{subject}相关业务数据。"
    if fpa_type == "EO":
        return f"输出{subject}相关业务数据。"
    return f"维护或处理{subject}相关业务数据。"


def _prompt_payload(
    group: dict[str, object],
    domain_context: dict[str, object] | None = None,
    profile_name: str = "strict_fpa",
    profile_kind: str = "strict_fpa",
) -> dict[str, object]:
    from ai_gen_reimbursement_docs.config_utils import load_fpa_adjustment_value_config
    from ai_gen_reimbursement_docs.fpa_agent_review import build_fpa_agent_review
    from ai_gen_reimbursement_docs.fpa_facts import extract_fpa_process_facts
    from ai_gen_reimbursement_docs.fpa_merge_review import build_fpa_merge_review
    from ai_gen_reimbursement_docs.fpa_type_judgement import build_fpa_type_judgement

    adjustment_config = load_fpa_adjustment_value_config()
    methods = adjustment_config.get("methods", {})
    standard_fpa = methods.get("standard_fpa", {}) if isinstance(methods, dict) else {}
    process_facts = extract_fpa_process_facts(group)
    merge_review = build_fpa_merge_review(group)
    type_judgement = build_fpa_type_judgement(group)
    agent_review = build_fpa_agent_review(
        group=group,
        profile_name=profile_name,
        profile_kind=profile_kind,
    )
    return {
        "module": {
            "client_type": group.get("client_type", ""),
            "l1": group.get("l1", ""),
            "l2": group.get("l2", ""),
            "l3": group.get("l3", ""),
            "l3_desc": group.get("l3_desc", ""),
        },
        "processes": [
            {
                "process_id": str(process.get("process_id", "") or ""),
                "process_name": str(process.get("process_name", "") or process.get("name", "") or ""),
                "description": str(process.get("description", "") or process.get("desc", "") or ""),
                "type": str(process.get("type", "") or ""),
            }
            for process in group.get("processes", [])
            if isinstance(process, dict)
        ] if isinstance(group.get("processes", []), list) else [],
        "process_facts": process_facts,
        "merge_review": merge_review,
        "type_judgement": type_judgement,
        "agent_review": agent_review,
        "domain_context": domain_context or {},
        "fpa_calculation": {
            "principles": [
                "以用户视角、业务意图和系统边界识别功能点。",
                "不要按按钮、页面、接口、数据库表、字段或代码组件机械计数。",
                "AI 只输出复杂度证据；最终调整值由系统代码按配置矩阵和权重表复算。",
            ],
            "types": {
                "ILF": "本系统内部维护的逻辑数据集合。",
                "EIF": "本系统引用但不维护的外部逻辑数据集合。",
                "EI": "外部输入，用于维护内部逻辑数据或改变系统状态。",
                "EO": "外部输出，包含派生计算、汇总、格式化处理或业务规则加工。",
                "EQ": "外部查询，输入查询条件并返回数据，不包含明显派生加工或状态改变。",
            },
            "metric_guidelines": {
                "DET": "用户可识别的数据项数量。",
                "RET": "ILF/EIF 中用户可识别的记录子组数量。",
                "FTR": "EI/EO/EQ 读取或维护的 ILF/EIF 数量。",
            },
            "adjustment_value_method_default": adjustment_config.get("method", ""),
            "standard_fpa": standard_fpa if isinstance(standard_fpa, dict) else {},
            "output_fields": {
                "ILF_EIF": ["complexity", "det_count", "ret_count", "complexity_reason"],
                "EI_EO_EQ": ["complexity", "det_count", "ftr_count", "complexity_reason"],
            },
            "constraints": [
                "不要自行编造未提供的复杂度矩阵或权重表。",
                "不要把 AI 返回的 FP 当作最终调整值。",
                "如果输入证据不足，输出保守复杂度并在 complexity_reason 中说明不确定点。",
                "不要模拟执行未提供的 rule_set_config；规则集由系统代码执行。",
            ],
        },
    }


def _numbered_judgement_rules(judgement_rules: list[str]) -> str:
    return "\n".join(f"{i}) {r}" for i, r in enumerate(judgement_rules, 1)) or "（无）"


def _render_configured_fpa_prompt(
    profile_name: str,
    profile_kind: str,
    core_rules: str,
    group: dict[str, object],
    judgement_rules: list[str],
    domain_context: dict[str, object] | None = None,
) -> str:
    import json
    from ai_gen_reimbursement_docs.config_utils import load_fpa_core_rules_config, load_fpa_user_prompt_template

    template = load_fpa_user_prompt_template(profile_name)
    configured_core_rules = load_fpa_core_rules_config(profile_name).text
    return Template(template).substitute({
        "core_rules": configured_core_rules or core_rules,
        "judgement_rules": _numbered_judgement_rules(judgement_rules),
        "payload_json": json.dumps(
            _prompt_payload(group, domain_context, profile_name, profile_kind),
            ensure_ascii=False,
            indent=2,
        ),
    })


def _external_rule_from_dict(item: dict[str, object]) -> ExternalDataGroupRule | None:
    aliases = item.get("source_aliases")
    data_name = str(item.get("data_name") or "").strip()
    data_nouns = item.get("data_nouns", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    if isinstance(data_nouns, str):
        data_nouns = [data_nouns]
    if not isinstance(aliases, list) or not data_name:
        return None
    alias_values = tuple(str(alias).strip() for alias in aliases if str(alias).strip())
    noun_values = tuple(str(noun).strip() for noun in data_nouns if str(noun).strip()) if isinstance(data_nouns, list) else ()
    if not alias_values:
        return None
    return ExternalDataGroupRule(alias_values, data_name, noun_values or tuple(EXTERNAL_DATA_GROUP_NOUNS))


def _keyword_rule_from_dict(item: dict[str, object]) -> KeywordTypeRule | None:
    fpa_type = str(item.get("type") or "").strip().upper()
    keywords = item.get("keywords", [])
    reason = str(item.get("reason") or "").strip()
    if not isinstance(keywords, list) or fpa_type not in VALID_TRANSACTION_FPA_TYPES:
        return None
    keyword_values = tuple(str(keyword).strip() for keyword in keywords if str(keyword).strip())
    if not keyword_values:
        return None
    return KeywordTypeRule(fpa_type, keyword_values, reason)


def _type_mapping_rule_from_dict(item: dict[str, object]) -> TypeMappingRule | None:
    fpa_type = str(item.get("type") or "").strip().upper()
    keywords = item.get("keywords", [])
    reason = str(item.get("reason") or "").strip()
    if not isinstance(keywords, list) or fpa_type not in VALID_FPA_TYPES:
        return None
    keyword_values = tuple(str(keyword).strip() for keyword in keywords if str(keyword).strip())
    if not keyword_values:
        return None
    return TypeMappingRule(fpa_type, keyword_values, reason)


def _ai_type_conflict_rule_from_dict(item: dict[str, object]) -> AiTypeConflictRule | None:
    expected_type = str(item.get("expected_type") or "").strip().upper()
    ai_type = str(item.get("ai_type") or "").strip().upper()
    keywords = item.get("keywords", [])
    conflict = item.get("conflict", True)
    reason = str(item.get("reason") or "").strip()
    if (
        expected_type not in VALID_FPA_TYPES
        or ai_type not in VALID_FPA_TYPES
        or not isinstance(keywords, list)
        or not isinstance(conflict, bool)
    ):
        return None
    keyword_values = tuple(str(keyword).strip() for keyword in keywords if str(keyword).strip())
    if not keyword_values:
        return None
    return AiTypeConflictRule(expected_type, ai_type, keyword_values, conflict, reason)


def _internal_data_rule_from_dict(item: dict[str, object]) -> InternalDataGroupRule | None:
    keywords = item.get("keywords", [])
    data_name = str(item.get("data_name") or "").strip()
    reason = str(item.get("reason") or "").strip()
    if not isinstance(keywords, list) or not data_name:
        return None
    keyword_values = tuple(str(keyword).strip() for keyword in keywords if str(keyword).strip())
    if not keyword_values:
        return None
    return InternalDataGroupRule(keyword_values, data_name, reason)


def _rule_section_from_dict(data: dict[str, object], key: str) -> tuple[str, list[object]]:
    section = data.get(key)
    if not isinstance(section, dict):
        return "append", []
    merge = str(section.get("merge") or "append").strip()
    items = section.get("items", [])
    return (merge if merge in VALID_RULE_MERGE_MODES else "append"), (items if isinstance(items, list) else [])


def _coverage_rules_from_dict(data: dict[str, object]) -> FpaCoverageRules:
    section = data.get("coverage_rules")
    if not isinstance(section, dict):
        return FpaCoverageRules()
    require_process_coverage = section.get("require_process_coverage")
    require_data_function = section.get("require_data_function")
    return FpaCoverageRules(
        require_process_coverage=require_process_coverage if isinstance(require_process_coverage, bool) else None,
        require_data_function=require_data_function if isinstance(require_data_function, bool) else None,
    )


def _ui_row_planning_rule_from_dict(section: object) -> FpaUiRowPlanningRule | None:
    if not isinstance(section, dict):
        return None
    return FpaUiRowPlanningRule(
        enabled=section.get("enabled") if isinstance(section.get("enabled"), bool) else None,
        scope=str(section.get("scope") or "").strip(),
        merge=str(section.get("merge") or "").strip(),
        name_suffix=str(section.get("name_suffix") or "").strip(),
        fpa_type=str(section.get("type") or "").strip().upper(),
        reason=str(section.get("reason") or "").strip(),
        empty_process_text=str(section.get("empty_process_text") or "").strip(),
        explanation_template=str(section.get("explanation_template") or "").strip(),
    )


def _process_rows_planning_rule_from_dict(section: object) -> FpaProcessRowsPlanningRule | None:
    if not isinstance(section, dict):
        return None
    raw_suffixes = section.get("type_suffixes")
    suffixes: dict[str, str] = {}
    if isinstance(raw_suffixes, dict):
        suffixes = {
            str(fpa_type).strip().upper(): str(suffix).strip()
            for fpa_type, suffix in raw_suffixes.items()
            if str(fpa_type).strip() and str(suffix).strip()
        }
    return FpaProcessRowsPlanningRule(
        enabled=section.get("enabled") if isinstance(section.get("enabled"), bool) else None,
        one_row_per_process=section.get("one_row_per_process")
        if isinstance(section.get("one_row_per_process"), bool)
        else None,
        default_name_suffix=str(section.get("default_name_suffix") or "").strip(),
        type_suffixes=suffixes,
        explanation_template=str(section.get("explanation_template") or "").strip(),
    )


def _row_planning_rules_from_dict(data: dict[str, object]) -> FpaRowPlanningRules:
    section = data.get("row_planning_rules")
    if not isinstance(section, dict):
        return FpaRowPlanningRules()
    return FpaRowPlanningRules(
        ui_row=_ui_row_planning_rule_from_dict(section.get("ui_row")),
        process_rows=_process_rows_planning_rule_from_dict(section.get("process_rows")),
    )


def _looks_like_ordinary_external_service(text: str) -> bool:
    upper_text = text.upper()
    return any(alias.upper() in upper_text for alias in ORDINARY_EXTERNAL_SERVICE_ALIASES)


def _external_data_rule_config_warnings(
    rule_set_name: str,
    rules: tuple[ExternalDataGroupRule, ...],
) -> tuple[str, ...]:
    warnings: list[str] = []
    for rule in rules:
        text = " ".join((*rule.source_aliases, rule.data_name, *rule.data_nouns))
        if not _looks_like_ordinary_external_service(text):
            continue
        aliases = "、".join(rule.source_aliases)
        warnings.append(
            "FPA 配置 warning: "
            f"rule_set {rule_set_name} 的 external_data_rules 将普通外部服务「{aliases}」"
            f"配置为外部数据组「{rule.data_name}」。配置仍会加载，但普通外部服务调用通常不应按 EIF 数据组计量。"
        )
    return tuple(warnings)


def _rule_set_from_dict(name: str, data: dict[str, object]) -> FpaRuleSetConfig:
    external_rules: list[ExternalDataGroupRule] = []
    external_merge, raw_external_rules = _rule_section_from_dict(data, "external_data_rules")
    for item in raw_external_rules:
        if isinstance(item, dict):
            rule = _external_rule_from_dict(item)
            if rule is not None:
                external_rules.append(rule)
    keyword_rules: list[KeywordTypeRule] = []
    keyword_merge, raw_keyword_rules = _rule_section_from_dict(data, "keyword_rules")
    for item in raw_keyword_rules:
        if isinstance(item, dict):
            rule = _keyword_rule_from_dict(item)
            if rule is not None:
                keyword_rules.append(rule)
    type_mapping_rules: list[TypeMappingRule] = []
    type_mapping_merge, raw_type_mapping_rules = _rule_section_from_dict(data, "type_mapping_rules")
    for item in raw_type_mapping_rules:
        if isinstance(item, dict):
            rule = _type_mapping_rule_from_dict(item)
            if rule is not None:
                type_mapping_rules.append(rule)
    ai_type_conflict_rules: list[AiTypeConflictRule] = []
    ai_type_conflict_merge, raw_ai_type_conflict_rules = _rule_section_from_dict(data, "ai_type_conflict_rules")
    for item in raw_ai_type_conflict_rules:
        if isinstance(item, dict):
            rule = _ai_type_conflict_rule_from_dict(item)
            if rule is not None:
                ai_type_conflict_rules.append(rule)
    internal_rules: list[InternalDataGroupRule] = []
    internal_merge, raw_internal_rules = _rule_section_from_dict(data, "internal_data_rules")
    for item in raw_internal_rules:
        if isinstance(item, dict):
            rule = _internal_data_rule_from_dict(item)
            if rule is not None:
                internal_rules.append(rule)
    return FpaRuleSetConfig(
        name=name,
        extends=str(data.get("extends") or "").strip(),
        external_data_rules=tuple(external_rules),
        external_data_rules_merge=external_merge,
        keyword_rules=tuple(keyword_rules),
        keyword_rules_merge=keyword_merge,
        type_mapping_rules=tuple(type_mapping_rules),
        type_mapping_rules_merge=type_mapping_merge,
        ai_type_conflict_rules=tuple(ai_type_conflict_rules),
        ai_type_conflict_rules_merge=ai_type_conflict_merge,
        internal_data_rules=tuple(internal_rules),
        internal_data_rules_merge=internal_merge,
        coverage_rules=_coverage_rules_from_dict(data),
        row_planning_rules=_row_planning_rules_from_dict(data),
        config_warnings=_external_data_rule_config_warnings(name, tuple(external_rules)),
        raw=dict(data),
    )


def _merge_coverage_rules(parent: FpaCoverageRules, child: FpaCoverageRules) -> FpaCoverageRules:
    return FpaCoverageRules(
        require_process_coverage=(
            child.require_process_coverage
            if child.require_process_coverage is not None
            else parent.require_process_coverage
        ),
        require_data_function=(
            child.require_data_function
            if child.require_data_function is not None
            else parent.require_data_function
        ),
    )


def _choose_configured_text(parent_value: str, child_value: str) -> str:
    return child_value if child_value else parent_value


def _merge_ui_row_planning_rule(
    parent: FpaUiRowPlanningRule | None,
    child: FpaUiRowPlanningRule | None,
) -> FpaUiRowPlanningRule | None:
    if child is None:
        return parent
    if parent is None:
        return child
    return FpaUiRowPlanningRule(
        enabled=child.enabled if child.enabled is not None else parent.enabled,
        scope=_choose_configured_text(parent.scope, child.scope),
        merge=_choose_configured_text(parent.merge, child.merge),
        name_suffix=_choose_configured_text(parent.name_suffix, child.name_suffix),
        fpa_type=_choose_configured_text(parent.fpa_type, child.fpa_type),
        reason=_choose_configured_text(parent.reason, child.reason),
        empty_process_text=_choose_configured_text(parent.empty_process_text, child.empty_process_text),
        explanation_template=_choose_configured_text(parent.explanation_template, child.explanation_template),
    )


def _merge_process_rows_planning_rule(
    parent: FpaProcessRowsPlanningRule | None,
    child: FpaProcessRowsPlanningRule | None,
) -> FpaProcessRowsPlanningRule | None:
    if child is None:
        return parent
    if parent is None:
        return child
    type_suffixes = dict(parent.type_suffixes)
    type_suffixes.update(child.type_suffixes)
    return FpaProcessRowsPlanningRule(
        enabled=child.enabled if child.enabled is not None else parent.enabled,
        one_row_per_process=(
            child.one_row_per_process if child.one_row_per_process is not None else parent.one_row_per_process
        ),
        default_name_suffix=_choose_configured_text(parent.default_name_suffix, child.default_name_suffix),
        type_suffixes=type_suffixes,
        explanation_template=_choose_configured_text(parent.explanation_template, child.explanation_template),
    )


def _merge_row_planning_rules(parent: FpaRowPlanningRules, child: FpaRowPlanningRules) -> FpaRowPlanningRules:
    return FpaRowPlanningRules(
        ui_row=_merge_ui_row_planning_rule(parent.ui_row, child.ui_row),
        process_rows=_merge_process_rows_planning_rule(parent.process_rows, child.process_rows),
    )


def _merge_rule_sets(parent: FpaRuleSetConfig, child: FpaRuleSetConfig) -> FpaRuleSetConfig:
    raw = dict(parent.raw)
    raw.update(child.raw)
    external_data_rules = _merge_rule_section(
        parent.external_data_rules,
        child.external_data_rules,
        child.external_data_rules_merge,
    )
    return FpaRuleSetConfig(
        name=child.name,
        extends=child.extends,
        external_data_rules=external_data_rules,
        external_data_rules_merge=child.external_data_rules_merge,
        keyword_rules=_merge_rule_section(parent.keyword_rules, child.keyword_rules, child.keyword_rules_merge),
        keyword_rules_merge=child.keyword_rules_merge,
        type_mapping_rules=_merge_rule_section(
            parent.type_mapping_rules,
            child.type_mapping_rules,
            child.type_mapping_rules_merge,
        ),
        type_mapping_rules_merge=child.type_mapping_rules_merge,
        ai_type_conflict_rules=_merge_rule_section(
            parent.ai_type_conflict_rules,
            child.ai_type_conflict_rules,
            child.ai_type_conflict_rules_merge,
        ),
        ai_type_conflict_rules_merge=child.ai_type_conflict_rules_merge,
        internal_data_rules=_merge_rule_section(
            parent.internal_data_rules,
            child.internal_data_rules,
            child.internal_data_rules_merge,
        ),
        internal_data_rules_merge=child.internal_data_rules_merge,
        coverage_rules=_merge_coverage_rules(parent.coverage_rules, child.coverage_rules),
        row_planning_rules=_merge_row_planning_rules(parent.row_planning_rules, child.row_planning_rules),
        config_warnings=_external_data_rule_config_warnings(child.name, external_data_rules),
        raw=raw,
    )


def _merge_rule_section(parent: tuple[object, ...], child: tuple[object, ...], merge: str) -> tuple[object, ...]:
    return child if merge == "replace" else (*parent, *child)


def load_configured_fpa_rule_sets() -> dict[str, FpaRuleSetConfig]:
    """读取用户配置的 FPA rule_set。"""
    try:
        from ai_gen_reimbursement_docs.config_utils import load_fpa_rule_sets_config
    except Exception:
        return {}

    raw_sets = load_fpa_rule_sets_config()
    configs: dict[str, FpaRuleSetConfig] = {}
    for name, data in raw_sets.items():
        if isinstance(data, dict) and str(name).strip():
            configs[str(name).strip()] = _rule_set_from_dict(str(name).strip(), data)
    return configs


def resolve_fpa_rule_set_config(rule_set: str) -> FpaRuleSetConfig:
    """解析 rule_set 配置，支持 extends 继承。"""
    configured = load_configured_fpa_rule_sets()
    resolving: list[str] = []

    def _resolve(name: str) -> FpaRuleSetConfig:
        if name in resolving:
            start = resolving.index(name)
            cycle_path = " -> ".join([*resolving[start:], name])
            raise ValueError(f"FPA rule_set 继承出现循环: {cycle_path}")
        resolving.append(name)
        try:
            current = configured.get(name)
            if current is None:
                raise ValueError(f"未知 FPA rule_set: {name}")
            if current.extends:
                parent = _resolve(current.extends)
                current = _merge_rule_sets(parent, current)
            return current
        finally:
            resolving.pop()

    return _resolve(rule_set)


def current_fpa_rule_set_config() -> FpaRuleSetConfig | None:
    return _CURRENT_RULE_SET_CONFIG.get()


def set_current_fpa_rule_set_config(config: FpaRuleSetConfig):
    return _CURRENT_RULE_SET_CONFIG.set(config)


def reset_current_fpa_rule_set_config(token) -> None:
    _CURRENT_RULE_SET_CONFIG.reset(token)


def _merge_source_process_text(existing: str, incoming: str) -> str:
    parts: list[str] = []
    for raw in [existing, incoming]:
        for item in str(raw or "").split("、"):
            value = item.strip()
            if value and value not in parts:
                parts.append(value)
    return "、".join(parts)


def _append_row_warning(row: dict[str, object], warning: str) -> None:
    current = str(row.get("后处理警告", "") or "").strip()
    if warning in current:
        return
    row["后处理警告"] = "；".join([part for part in [current, warning] if part])


def _append_row_with_l3_name_policy(rows: list[dict[str, object]], row: dict[str, object]) -> bool:
    """同一三级模块内，同名同类型合并来源；同名不同类型保留并提示。"""
    name = str(row.get("新增/修改功能点", "") or "")
    fpa_type = str(row.get("类型", "") or "")
    same_name_rows = [
        existing
        for existing in rows
        if str(existing.get("新增/修改功能点", "") or "") == name
    ]
    for existing in same_name_rows:
        if str(existing.get("类型", "") or "") == fpa_type:
            existing["源功能过程"] = _merge_source_process_text(
                str(existing.get("源功能过程", "") or ""),
                str(row.get("源功能过程", "") or ""),
            )
            return False
    if same_name_rows:
        warning = f"{name} 同名不同类型结果行，已保留并提示人工审阅。"
        for existing in same_name_rows:
            _append_row_warning(existing, warning)
        _append_row_warning(row, warning)
    rows.append(row)
    return True


@dataclass(frozen=True)
class CustomRulesProfile:
    """用户自定义规则口径。"""

    name: str = "unified_ui"
    version: str = "1"
    description: str = "统一界面口径：三级模块合并界面能力，非界面逻辑按动作拆分。"
    core_rules: str = UNIFIED_UI_CORE_RULES

    def infer_type(self, name: str, desc: str = "") -> tuple[str, str]:
        """按当前项目关键词规则给出类型兜底。"""
        text = f"{name} {desc}"
        type_mapping = self._configured_type_mapping(text, include_types={"EI", "EQ", "EO", "EIF"})
        if type_mapping:
            return type_mapping
        for rule in self._configured_keyword_rules():
            if rule.matches(text):
                return rule.fpa_type, rule.reason or f"命中 rule_set 关键词规则，按 {rule.fpa_type}。"
        type_mapping = self._configured_type_mapping(text)
        if type_mapping:
            return type_mapping
        return "ILF", "未命中明确类型关键词，按 ILF 兜底。"

    def has_obvious_conflict(self, name: str, desc: str, ai_type: str) -> bool:
        expected, _ = self.infer_type(name, desc)
        if "外部接口" in f"{name} {desc}" and expected == "ILF":
            return ai_type == "EIF"
        return expected != ai_type and any(
            k in f"{name} {desc}"
            for k in ["界面开发", "导出", "导入", "查询", "查看", "详情", "添加", "新增", "编辑", "删除", "维护", "保存"]
        )

    def ai_data_group_review_warning(self, name: str, desc: str, ai_type: str) -> str:
        return ""

    def logic_point_name(self, name: str, desc: str = "") -> str:
        text = f"{name} {desc}"
        process_rule = self._configured_process_row_planning_rule()
        if process_rule is None or process_rule.enabled is False:
            return name
        for rule in self._configured_keyword_rules():
            if not rule.matches(text):
                continue
            suffix = process_rule.type_suffixes.get(rule.fpa_type)
            if suffix:
                return f"{name}-{suffix}"
        return f"{name}-{process_rule.default_name_suffix}" if process_rule.default_name_suffix else name

    def normalize_output_name(self, name: str, desc: str = "") -> str:
        return name

    def fallback_rows_for_l3(
        self,
        group: dict[str, object],
        meta: dict[str, str],
        start_seq: int = 1,
    ) -> list[dict[str, object]]:
        """AI 不可用或失败时的三级模块兜底 FPA 行。"""
        subsystem = meta.get("子系统（模块）", "")
        asset = meta.get("资产标识", "")
        tag = group_tag(group)
        processes = group.get("processes", [])
        process_list = processes if isinstance(processes, list) else []
        rows: list[dict[str, object]] = []
        seq = start_seq

        ui_rule = self._configured_ui_row_planning_rule()
        if ui_rule is not None and ui_rule.enabled is not False:
            ui_items = []
            for p in process_list:
                if not isinstance(p, dict):
                    continue
                name = str(p.get("name", "") or "").strip()
                desc = str(p.get("desc", "") or "").strip()
                if name or desc:
                    ui_items.append(desc or name)
            ui_detail = "\n".join(
                f"{i}、{item}" for i, item in enumerate(ui_items or [ui_rule.empty_process_text], 1) if item
            )
            ui_name = f"{tag}-{ui_rule.name_suffix}" if ui_rule.name_suffix else tag
            rows.append({
                "序号": seq,
                "子系统(模块)": subsystem,
                "资产标识": asset,
                "新增/修改功能点": ui_name,
                "类型": ui_rule.fpa_type,
                "计算依据归类": "",
                "计算依据说明": ui_rule.explanation_template.format(name=ui_name, items=ui_detail),
                "变更状态": module_change_status(process_list),
                "调整值": adjust_value_for_type(ui_rule.fpa_type),
                "要素数量": 1,
                "生成方式": "fallback",
                "类型理由": ui_rule.reason,
                "源功能过程": "、".join(str(p.get("name", "")) for p in process_list if isinstance(p, dict)),
                "后处理警告": "",
            })
            seq += 1

        process_rule = self._configured_process_row_planning_rule()
        if process_rule is None or process_rule.enabled is False:
            return _structure_fallback_explanations(group, rows)
        for p in process_list:
            if not isinstance(p, dict):
                continue
            name = str(p.get("name", "") or "").strip()
            desc = str(p.get("desc", "") or "").strip()
            if not name:
                continue
            point_name = function_point_tag(group, self.logic_point_name(name, desc))
            fpa_type, reason = self.infer_type(point_name, desc)
            row = {
                "序号": seq,
                "子系统(模块)": subsystem,
                "资产标识": asset,
                "新增/修改功能点": point_name,
                "类型": fpa_type,
                "计算依据归类": "",
                "计算依据说明": process_rule.explanation_template.format(
                    name=point_name,
                    description=desc or name,
                ),
                "变更状态": str(p.get("type", "") or module_change_status(process_list)),
                "调整值": adjust_value_for_type(fpa_type),
                "要素数量": 1,
                "生成方式": "fallback",
                "类型理由": reason,
                "源功能过程": name,
                "后处理警告": "",
            }
            if _append_row_with_l3_name_policy(rows, row):
                seq += 1
        return _structure_fallback_explanations(group, rows)

    def build_prompt(
        self,
        group: dict[str, object],
        judgement_rules: list[str],
        domain_context: dict[str, object] | None = None,
    ) -> str:
        return _render_configured_fpa_prompt(
            self.name,
            self.agent_review_profile_kind(),
            self.core_rules,
            group,
            judgement_rules,
            domain_context,
        )

    def agent_review_profile_kind(self) -> str:
        return "unified_ui"

    def _configured_keyword_rules(self) -> tuple[KeywordTypeRule, ...]:
        current_rule_set = current_fpa_rule_set_config()
        return current_rule_set.keyword_rules if current_rule_set is not None else ()

    def _configured_type_mapping_rules(self) -> tuple[TypeMappingRule, ...]:
        current_rule_set = current_fpa_rule_set_config()
        return current_rule_set.type_mapping_rules if current_rule_set is not None else ()

    def _configured_ui_row_planning_rule(self) -> FpaUiRowPlanningRule | None:
        current_rule_set = current_fpa_rule_set_config()
        return current_rule_set.row_planning_rules.ui_row if current_rule_set is not None else None

    def _configured_process_row_planning_rule(self) -> FpaProcessRowsPlanningRule | None:
        current_rule_set = current_fpa_rule_set_config()
        return current_rule_set.row_planning_rules.process_rows if current_rule_set is not None else None

    def _configured_type_mapping(
        self,
        text: str,
        include_types: set[str] | None = None,
    ) -> tuple[str, str] | None:
        for rule in self._configured_type_mapping_rules():
            if include_types is not None and rule.fpa_type not in include_types:
                continue
            if rule.matches(text):
                return rule.fpa_type, rule.reason or f"命中 rule_set 类型映射规则，按 {rule.fpa_type}。"
        return None


@dataclass(frozen=True)
class StrictFpaProfile(CustomRulesProfile):
    """严格 FPA 口径。"""

    name: str = "strict_fpa"
    version: str = "1"
    description: str = "严格 FPA 口径：按数据功能和事务功能拆分，不按界面/接口开发工作项拆分。"
    core_rules: str = STRICT_FPA_CORE_RULES

    def _has_explicit_transaction_action(self, text: str) -> bool:
        return any(k in text for k in [
            "新增", "添加", "修改", "编辑", "删除", "维护", "保存", "提交", "审批",
            "启用", "停用", "导入", "同步", "发起", "写入", "选择", "引用", "关联",
            "查询", "查看", "详情", "检索", "列表", "导出", "下载", "生成文件", "打印",
        ])

    def infer_type(self, name: str, desc: str = "") -> tuple[str, str]:
        text = f"{name} {desc}"
        name_is_data_group = self._looks_like_data_group(name)
        point_tail = self._function_point_tail(name)
        name_action = self._explicit_transaction_type(point_tail)
        if name_action and self._has_explicit_transaction_action(point_tail) and not name_is_data_group:
            return name_action
        type_mapping = self._configured_type_mapping(text)
        if type_mapping:
            return type_mapping
        if self._has_internal_data_function(text) and name_is_data_group:
            return "ILF", "本系统维护的逻辑数据组，按 ILF。"
        if self._looks_like_external_data_function_name(name) and self._is_external_data_group(text):
            return "EIF", "明确引用外部系统维护的数据组，按 EIF。"
        if name_is_data_group and self._is_external_data_group(text):
            return "EIF", "明确引用外部系统维护的数据组，按 EIF。"
        internal_rule = self._matching_internal_data_rule(text)
        if internal_rule is not None and name_is_data_group:
            return "ILF", internal_rule.reason or "命中 rule_set 内部数据组规则，按 ILF。"
        if name_is_data_group or self._looks_like_data_group(name, desc):
            return "ILF", "本系统维护的逻辑数据组，按 ILF。"
        desc_action = self._explicit_transaction_type(desc)
        if desc_action:
            return desc_action
        if any(k in text for k in EXTERNAL_SERVICE_CALL_HINTS):
            return "EI", "普通外部服务调用按触发事务处理，不能直接判 EIF。"
        return "EI", "未命中明确数据功能关键词，按事务功能 EI 兜底。"

    def _explicit_transaction_type(self, text: str) -> tuple[str, str] | None:
        eo_match = self._matching_keyword_rule(text, "EO")
        if eo_match is not None:
            return eo_match.fpa_type, eo_match.reason or "事务功能产生派生或格式化输出，按 EO。"
        eq_start_match = self._matching_keyword_rule(text, "EQ", startswith=True)
        if eq_start_match is not None:
            return eq_start_match.fpa_type, eq_start_match.reason or "事务功能读取数据且无派生输出，按 EQ。"
        ei_match = self._matching_keyword_rule(text, "EI")
        if ei_match is not None:
            return ei_match.fpa_type, ei_match.reason or "事务功能进入或改变系统边界内数据，按 EI。"
        eq_match = self._matching_keyword_rule(text, "EQ")
        if eq_match is not None:
            return eq_match.fpa_type, eq_match.reason or "事务功能读取数据且无派生输出，按 EQ。"
        if any(k in text for k in ("导出", "下载", "生成文件", "打印")):
            return "EO", "事务功能产生派生或格式化输出，按 EO。"
        if any(k in text for k in ("查询", "查看", "详情", "检索", "列表")):
            return "EQ", "事务功能读取数据且无派生输出，按 EQ。"
        if any(k in text for k in (
            "新增", "添加", "修改", "编辑", "删除", "维护", "保存", "提交", "审批",
            "启用", "停用", "导入", "同步", "发起", "写入", "选择", "引用", "关联",
        )):
            return "EI", "事务功能进入或改变系统边界内数据，按 EI。"
        return None

    def _matching_keyword_rule(
        self,
        text: str,
        fpa_type: str,
        startswith: bool = False,
    ) -> KeywordTypeRule | None:
        stripped = text.strip()
        for rule in self._configured_keyword_rules():
            if rule.fpa_type != fpa_type:
                continue
            if startswith and any(stripped.startswith(keyword) for keyword in rule.keywords):
                return rule
            if not startswith and rule.matches(text):
                return rule
        return None

    def _looks_like_external_data_function_name(self, name: str) -> bool:
        point_name = self._function_point_tail(name)
        action_keywords = self._configured_transaction_keywords()
        if "数据组" in point_name:
            return any(noun in point_name for noun in EXTERNAL_DATA_GROUP_NOUNS)
        return (
            any(noun in point_name for noun in EXTERNAL_DATA_GROUP_NOUNS)
            and not any(action in point_name for action in action_keywords)
        )

    def has_obvious_conflict(self, name: str, desc: str, ai_type: str) -> bool:
        text = f"{name} {desc}"
        if any(k in text for k in ["界面开发", "接口开发", "逻辑处理开发", "按钮", "弹窗"]):
            return True
        if any(k in text for k in EXTERNAL_SERVICE_CALL_HINTS):
            return ai_type == "EIF"
        expected_type = self._conflict_matrix_expected_type(name, desc)
        if expected_type is None:
            return False
        configured_conflict = self._configured_ai_type_conflict(text, expected_type, ai_type)
        if configured_conflict is not None:
            return configured_conflict
        return self._type_conflicts(expected_type, ai_type)

    def _conflict_matrix_expected_type(self, name: str, desc: str) -> str | None:
        text = f"{name} {desc}"
        name_is_data_group = self._looks_like_data_group(name)
        point_tail = self._function_point_tail(name)
        name_action = self._explicit_transaction_type(point_tail)
        if name_action and self._has_explicit_transaction_action(point_tail) and not name_is_data_group:
            return name_action[0]
        type_mapping = self._configured_type_mapping(text)
        if type_mapping:
            return type_mapping[0]
        if self._has_internal_data_function(text) and name_is_data_group:
            return "ILF"
        if self._looks_like_external_data_function_name(name) and self._is_external_data_group(text):
            return "EIF"
        if name_is_data_group and self._is_external_data_group(text) and self._looks_like_external_data_function_name(name):
            return "EIF"
        if self._matching_internal_data_rule(text) is not None and name_is_data_group:
            return "ILF"
        if name_is_data_group or self._looks_like_data_group(name, desc):
            return "ILF"
        desc_action = self._explicit_transaction_type(desc)
        if desc_action:
            return desc_action[0]
        return None

    def _type_conflicts(self, expected_type: str, ai_type: str) -> bool:
        ai_type = ai_type.upper()
        if ai_type not in {"EI", "EQ", "EO", "ILF", "EIF"}:
            return True
        if expected_type == ai_type:
            return False
        conflict_matrix = {
            "EI": {"EQ", "EO", "ILF", "EIF"},
            "EQ": {"EI", "EO", "ILF", "EIF"},
            "EO": {"EI", "EQ", "ILF", "EIF"},
            "ILF": {"EI", "EQ", "EO", "EIF"},
            "EIF": {"EI", "EQ", "EO", "ILF"},
        }
        return ai_type in conflict_matrix.get(expected_type, set())

    def ai_data_group_review_warning(self, name: str, desc: str, ai_type: str) -> str:
        ai_type = ai_type.upper()
        if ai_type not in {"ILF", "EIF"}:
            return ""
        text = f"{name} {desc}"
        if ai_type == "EIF" and any(rule.matches(text) for rule in self._external_data_group_rules()):
            return ""
        if ai_type == "ILF" and (
            self._matching_internal_data_rule(text) is not None
            or self._looks_like_data_group(name)
        ):
            return ""
        return f"{name} AI 数据功能需人工复核：AI type={ai_type}，当前规则未能确认该数据组边界。"

    def logic_point_name(self, name: str, desc: str = "") -> str:
        return name

    def normalize_output_name(self, name: str, desc: str = "") -> str:
        return self._transaction_name(name)

    def fallback_rows_for_l3(
        self,
        group: dict[str, object],
        meta: dict[str, str],
        start_seq: int = 1,
    ) -> list[dict[str, object]]:
        subsystem = meta.get("子系统（模块）", "")
        asset = meta.get("资产标识", "")
        processes = group.get("processes", [])
        process_list = processes if isinstance(processes, list) else []
        rows: list[dict[str, object]] = []
        seq = start_seq

        for data_name, data_type, data_reason in self._data_functions_for_group(group, process_list):
            point_name = function_point_tag(group, data_name)
            rows.append({
                "序号": seq,
                "子系统(模块)": subsystem,
                "资产标识": asset,
                "新增/修改功能点": point_name,
                "类型": data_type,
                "计算依据归类": "",
                "计算依据说明": f"{point_name}，作为该三级模块涉及的逻辑数据组。",
                "变更状态": module_change_status(process_list),
                "调整值": adjust_value_for_type(data_type),
                "要素数量": 1,
                "生成方式": "fallback",
                "类型理由": data_reason,
                "源功能过程": "、".join(str(p.get("name", "")) for p in process_list if isinstance(p, dict)),
                "后处理警告": "",
            })
            seq += 1

        for transaction in self._logical_transactions_for_group(process_list):
            point_name = function_point_tag(group, str(transaction["name"]))
            row = {
                "序号": seq,
                "子系统(模块)": subsystem,
                "资产标识": asset,
                "新增/修改功能点": point_name,
                "类型": transaction["type"],
                "计算依据归类": "",
                "计算依据说明": str(transaction["explanation"]).replace(str(transaction["name"]), point_name, 1),
                "变更状态": str(transaction["change_status"] or module_change_status(process_list)),
                "调整值": adjust_value_for_type(str(transaction["type"])),
                "要素数量": 1,
                "生成方式": "fallback",
                "类型理由": transaction["reason"],
                "源功能过程": transaction["sources"],
                "后处理警告": "",
            }
            if _append_row_with_l3_name_policy(rows, row):
                seq += 1
        return _structure_fallback_explanations(group, rows)

    def _logical_transactions_for_group(self, process_list: list[object]) -> list[dict[str, object]]:
        singles: list[dict[str, object]] = []
        grouped: dict[tuple[str, str], list[dict[str, object]]] = {}

        for p in process_list:
            if not isinstance(p, dict):
                continue
            raw_name = str(p.get("name", "") or "").strip()
            desc = str(p.get("desc", "") or "").strip()
            if not raw_name:
                continue
            point_name = self._transaction_name(raw_name)
            fpa_type, reason = self.infer_type(point_name, desc)
            if fpa_type in {"ILF", "EIF"}:
                fpa_type = "EI"
                reason = "功能过程按事务功能计量，数据功能已单独识别。"
            item = {
                "raw_name": raw_name,
                "point_name": point_name,
                "desc": desc,
                "type": fpa_type,
                "reason": reason,
                "change_status": str(p.get("type", "") or ""),
            }
            group_key = self._logical_transaction_group_key(point_name, desc, fpa_type)
            if group_key is None:
                singles.append(self._single_transaction_row(item))
                continue
            if group_key not in grouped:
                grouped[group_key] = []
            grouped[group_key].append(item)

        result: list[dict[str, object]] = []
        single_iter = iter(singles)
        emitted_group_keys: set[tuple[str, str]] = set()
        for p in process_list:
            if not isinstance(p, dict):
                continue
            raw_name = str(p.get("name", "") or "").strip()
            if not raw_name:
                continue
            point_name = self._transaction_name(raw_name)
            fpa_type, _ = self.infer_type(point_name, str(p.get("desc", "") or "").strip())
            if fpa_type in {"ILF", "EIF"}:
                fpa_type = "EI"
            group_key = self._logical_transaction_group_key(point_name, str(p.get("desc", "") or "").strip(), fpa_type)
            if group_key is None:
                result.append(next(single_iter))
                continue
            if group_key in emitted_group_keys:
                continue
            emitted_group_keys.add(group_key)
            items = grouped[group_key]
            result.append(
                self._merged_transaction_row(group_key, items)
                if len(items) > 1
                else self._single_transaction_row(items[0])
            )
        return result

    def _single_transaction_row(self, item: dict[str, object]) -> dict[str, object]:
        point_name = str(item["point_name"])
        desc = str(item["desc"] or item["raw_name"])
        return {
            "name": point_name,
            "type": item["type"],
            "reason": item["reason"],
            "explanation": f"{point_name}，具体为以下：\n1、{desc}",
            "change_status": item["change_status"],
            "sources": item["raw_name"],
        }

    def _merged_transaction_row(
        self,
        group_key: tuple[str, str],
        items: list[dict[str, object]],
    ) -> dict[str, object]:
        fpa_type, object_name = group_key
        suffix = "查询" if fpa_type == "EQ" else "维护" if fpa_type == "EI" else "输出"
        point_name = f"{object_name}{suffix}"
        detail = "\n".join(
            f"{i}、{str(item['desc'] or item['raw_name'])}"
            for i, item in enumerate(items, 1)
        )
        sources = "、".join(str(item["raw_name"]) for item in items)
        if fpa_type == "EQ":
            reason = "多个查询功能过程读取同一业务对象并展示同类结果，按一个逻辑查询事务 EQ 合并。"
        elif fpa_type == "EI":
            reason = "多个维护功能过程针对同一业务对象改变系统内数据，按一个逻辑维护事务 EI 合并。"
        else:
            reason = "多个输出功能过程针对同一业务对象，按一个逻辑输出事务 EO 合并。"
        return {
            "name": point_name,
            "type": fpa_type,
            "reason": reason,
            "explanation": f"{point_name}，合并以下同一逻辑事务：\n{detail}",
            "change_status": next((str(item["change_status"]) for item in items if str(item["change_status"])), ""),
            "sources": sources,
        }

    def _logical_transaction_group_key(
        self,
        name: str,
        desc: str,
        fpa_type: str,
    ) -> tuple[str, str] | None:
        if fpa_type not in {"EI", "EQ"}:
            return None
        object_name = self._transaction_object_name(name)
        if not object_name:
            object_name = self._transaction_object_name(desc)
        if not object_name:
            return None
        return fpa_type, object_name

    def _transaction_object_name(self, text: str) -> str:
        value = text.strip()
        if not value:
            return ""
        value = re.sub(
            r"(?:新增|添加|修改|编辑|删除|维护|保存|提交|审批|启用|停用|导入|同步|发起|写入|选择|引用|关联|查询|查看|详情|检索|列表)",
            "",
            value,
        )
        value = re.sub(r"(?:数据查询|数据|信息|记录|列表|详情|结果|指定|当前|已保存的|存量的)", "", value)
        value = re.split(r"[，。；、\s]", value, maxsplit=1)[0]
        return value.strip(" 的。；，、")

    def build_prompt(
        self,
        group: dict[str, object],
        judgement_rules: list[str],
        domain_context: dict[str, object] | None = None,
    ) -> str:
        return _render_configured_fpa_prompt(
            self.name,
            self.agent_review_profile_kind(),
            self.core_rules,
            group,
            judgement_rules,
            domain_context,
        )

    def agent_review_profile_kind(self) -> str:
        return "strict_fpa"

    def _is_external_data_group(self, text: str) -> bool:
        if any(k in text for k in EXTERNAL_DATA_NEGATION_HINTS):
            return False
        has_external_source = any(rule.matches(text) for rule in self._external_data_group_rules())
        has_maintenance_hint = any(k in text for k in EXTERNAL_MAINTAINED_HINTS)
        has_generic_external_maintenance = bool(
            re.search(r"(?:外部应用|外部系统|第三方系统|外部|第三方)[^，。；、\s]{0,16}(?:维护|提供)", text)
        )
        has_data_noun = any(k in text for k in EXTERNAL_DATA_GROUP_NOUNS)
        return has_data_noun and (has_external_source or has_maintenance_hint or has_generic_external_maintenance)

    def _looks_like_data_group(self, name: str, desc: str = "") -> bool:
        point_name = self._function_point_tail(name)
        text = f"{name} {desc}"
        if (
            any(k in text for k in EXTERNAL_MAINTAINED_HINTS)
            or re.search(r"(?:外部应用|外部系统|第三方系统|外部|第三方)[^，。；、\s]{0,16}(?:维护|提供)", text)
        ) and not self._has_internal_data_function(text):
            return False
        if any(k in point_name for k in ["信息", "数据组", "主数据", "名单", "档案", "关系", "配置", "记录", "模板"]):
            return not any(
                k in point_name
                for k in ["查询", "查看", "详情", "新增", "添加", "修改", "编辑", "删除", "维护", "保存", "配置", "导入", "导出"]
            )
        return False

    def _function_point_tail(self, name: str) -> str:
        return str(name or "").rsplit("-", maxsplit=1)[-1].strip()

    def _data_functions_for_group(
        self,
        group: dict[str, object],
        process_list: list[object],
    ) -> list[tuple[str, str, str]]:
        l3 = str(group.get("l3", "") or "").strip()
        l3_desc = str(group.get("l3_desc", "") or "").strip()
        all_text = " ".join(
            [l3, l3_desc]
            + [
                f"{p.get('name', '')} {p.get('desc', '')}"
                for p in process_list
                if isinstance(p, dict)
            ]
        )
        data_functions: list[tuple[str, str, str]] = []
        synced_local_names = self._synced_local_data_names(all_text)
        if synced_local_names:
            for local_name in synced_local_names:
                data_functions.append((
                    local_name,
                    "ILF",
                    "外部数据同步进入本系统后继续维护，按本系统 ILF。",
                ))
        else:
            for external_name in self._external_data_names(all_text, l3):
                data_functions.append((
                    external_name,
                    "EIF",
                    "外部系统维护、本系统引用的数据组，按 EIF。",
                ))
        for rule in self._configured_internal_data_rules():
            if rule.matches(all_text):
                data_functions.append((
                    rule.data_name,
                    "ILF",
                    rule.reason or "命中 rule_set 内部数据组规则，按 ILF。",
                ))
        if self._has_internal_data_function(all_text) or (
            not data_functions
            and any(k in all_text for k in ["维护", "保存", "新增", "添加", "修改", "编辑", "删除", "导入", "配置"])
        ):
            data_functions.append((
                self._internal_data_name(l3),
                "ILF",
                "本系统维护的逻辑数据组，按 ILF。",
            ))
        for extra_name in self._extra_internal_data_names(l3, process_list):
            data_functions.append((
                extra_name,
                "ILF",
                "本系统维护的关联逻辑数据组，按 ILF。",
            ))
        return self._dedupe_data_functions(data_functions)

    def _internal_data_name(self, l3: str) -> str:
        if not l3:
            return "业务数据组"
        name = l3.replace("管理", "").replace("维护", "").strip()
        if not name:
            name = l3
        if name.endswith("关联"):
            return f"{name}关系"
        if any(k in name for k in ["信息", "数据组", "主数据", "名单", "档案", "关系", "配置", "记录", "模板"]):
            return name
        return f"{name}信息"

    def _external_data_name(self, text: str, fallback: str) -> str:
        for rule in self._external_data_group_rules():
            if rule.matches(text):
                return rule.data_name
        extracted = self._extract_external_data_name(text)
        if extracted:
            return extracted
        name = fallback or "外部维护数据组"
        return name if "数据组" in name else f"{name}数据组"

    def _external_data_names(self, text: str, fallback: str) -> list[str]:
        if not self._is_external_data_group(text):
            return []
        names: list[str] = []
        for rule in self._external_data_group_rules():
            if rule.matches(text):
                names.append(rule.data_name)
        if not names:
            names.extend(self._extract_external_data_names(text))
        if not names:
            name = fallback or "外部维护数据组"
            names.append(name if "数据组" in name else f"{name}数据组")
        if len(names) > 1 and "外部主数据" in names:
            names = [name for name in names if name != "外部主数据"]
        result: list[str] = []
        seen: set[str] = set()
        for name in names:
            if name and name not in seen:
                seen.add(name)
                result.append(name)
        return result

    def _has_internal_data_function(self, text: str) -> bool:
        if re.search(r"(?:外部|第三方|CRM|ERP|OA|主数据平台|统一用户中心)[^，。；、\s]{0,24}维护本系统引用", text):
            return False
        if re.search(r"本系统引用[^，。；、\s]{0,24}(?:维护|提供)", text):
            return False
        return any(k in text for k in [
            "本系统维护", "本系统保存", "本系统只保存", "本系统继续维护",
            "本系统创建并维护", "本系统内部创建", "本系统内部维护", "本系统唯一维护",
            "本系统后台数据库新增", "本系统后台数据库变更", "本系统后台数据库新增或变更",
            "本系统内创建关联记录", "本系统内创建", "本系统内新增", "本系统内保存",
            "系统内部创建", "系统内部维护", "系统唯一维护",
            "维护本系统", "记录本系统",
        ])

    def _external_data_group_rules(self) -> list[ExternalDataGroupRule]:
        current_rule_set = current_fpa_rule_set_config()
        return list(current_rule_set.external_data_rules) if current_rule_set is not None else []

    def _configured_keyword_rules(self) -> tuple[KeywordTypeRule, ...]:
        rules = super()._configured_keyword_rules()
        if rules:
            return rules
        return (
            KeywordTypeRule("EO", ("导出", "报表", "下载", "生成文件"), "事务功能产生派生或格式化输出，按 EO。"),
            KeywordTypeRule("EQ", ("查询", "查看", "详情", "检索", "列表"), "事务功能读取数据且无派生输出，按 EQ。"),
            KeywordTypeRule(
                "EI",
                ("新增", "添加", "修改", "编辑", "删除", "维护", "保存", "提交", "审批", "启用", "停用", "导入", "同步", "发起", "写入", "选择", "引用", "关联"),
                "事务功能进入或改变系统边界内数据，按 EI。",
            ),
        )

    def _configured_transaction_keywords(self) -> tuple[str, ...]:
        keywords: list[str] = []
        for rule in self._configured_keyword_rules():
            keywords.extend(rule.keywords)
        return tuple(keywords)

    def _configured_type_mapping_rules(self) -> tuple[TypeMappingRule, ...]:
        return super()._configured_type_mapping_rules()

    def _configured_type_mapping(
        self,
        text: str,
        include_types: set[str] | None = None,
    ) -> tuple[str, str] | None:
        return super()._configured_type_mapping(text, include_types)

    def _configured_ai_type_conflict_rules(self) -> tuple[AiTypeConflictRule, ...]:
        current_rule_set = current_fpa_rule_set_config()
        return current_rule_set.ai_type_conflict_rules if current_rule_set is not None else ()

    def _configured_ai_type_conflict(self, text: str, expected_type: str, ai_type: str) -> bool | None:
        for rule in self._configured_ai_type_conflict_rules():
            if rule.matches(text, expected_type, ai_type):
                return rule.conflict
        return None

    def _configured_internal_data_rules(self) -> tuple[InternalDataGroupRule, ...]:
        current_rule_set = current_fpa_rule_set_config()
        return current_rule_set.internal_data_rules if current_rule_set is not None else ()

    def _matching_internal_data_rule(self, text: str) -> InternalDataGroupRule | None:
        for rule in self._configured_internal_data_rules():
            if rule.matches(text):
                return rule
        return None

    def _extract_external_data_name(self, text: str) -> str:
        names = self._extract_external_data_names(text)
        return names[0] if names else ""

    def _extract_external_data_names(self, text: str) -> list[str]:
        patterns = [
            r"(?:外部应用|外部系统|第三方系统|外部|第三方)[^，。；、\s]{0,16}(?:维护|提供)的?([^，。；、\s]{2,24}(?:数据组|主数据|基础数据|档案|信息|记录|账号|账户|单据))",
            r"(?:引用|读取|使用|选择|同步)([^，。；、\s]{2,24}(?:数据组|主数据|基础数据|档案|信息|记录|账号|账户|单据))",
            r"([^，。；、\s]{2,24}(?:数据组|主数据|基础数据|档案|信息|记录|账号|账户|单据))(?:由|为)?(?:外部应用|外部系统|第三方系统|外部|第三方)[^，。；、\s]{0,12}(?:维护|提供)",
            r"(?:本系统不维护)([^，。；、\s]{2,24}(?:数据组|主数据|基础数据|档案|信息|记录|账号|账户|单据))",
        ]
        names: list[str] = []
        seen: set[str] = set()
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                name = self._clean_external_data_name(match.group(1))
                if name and name not in seen:
                    seen.add(name)
                    names.append(name)
        return names

    def _clean_external_data_name(self, name: str) -> str:
        name = re.sub(r"^(?:外部应用|外部系统|第三方系统|外部|第三方)[^，。；、\s]{0,16}(?:维护|提供)的?", "", name)
        for prefix in ["外部应用维护的", "外部系统维护的", "第三方系统维护的", "外部维护的", "本系统不维护的"]:
            if name.startswith(prefix):
                name = name[len(prefix):]
        name = re.split(r"(?:中选择|中查看|中读取|并|，|。|；|、)", name, maxsplit=1)[0]
        return name.strip(" 的。；，、")

    def _synced_local_data_names(self, text: str) -> list[str]:
        if "同步" not in text or not any(k in text for k in ["本系统继续维护", "写入本系统", "本系统保存", "本系统维护"]):
            return []
        patterns = [
            r"(?:写入|保存到|维护|查看)(?:本系统)?([^，。；、\s]{2,24}(?:本地档案|扩展信息|本地信息|本地记录|本地数据|档案|信息|记录))",
            r"(?:本系统继续维护)([^，。；、\s]{2,24}(?:本地档案|扩展信息|本地信息|本地记录|本地数据|档案|信息|记录))",
        ]
        names: list[str] = []
        seen: set[str] = set()
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                name = match.group(1).strip(" 的。；，、")
                if name and name not in seen:
                    seen.add(name)
                    names.append(name)
        return names

    def _extra_internal_data_names(self, l3: str, process_list: list[object]) -> list[str]:
        base = self._internal_data_name(l3)
        if base.endswith("信息"):
            base = base[:-2]
        names: list[str] = []
        for p in process_list:
            if not isinstance(p, dict):
                continue
            text = f"{p.get('name', '')} {p.get('desc', '')}"
            if "管理员" in text:
                names.append(f"{base}管理员关系")
            if any(k in text for k in ["关联关系", "匹配关系", "映射关系", "绑定关系"]):
                relation_name = self._extract_relation_data_name(text)
                if relation_name:
                    names.append(relation_name)
                else:
                    names.append(self._relation_data_name(l3))
        return names

    def _extract_relation_data_name(self, text: str) -> str:
        patterns = [
            r"(?:本系统)?(?:保存|维护|记录|查看已保存的)([^，。；、\s]{2,24}(?:关联关系|匹配关系|映射关系|绑定关系))",
            r"(?:本系统)?(?:保存|维护|记录)([^，。；、\s]{2,16})的(关联关系|匹配关系|映射关系|绑定关系)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            if len(match.groups()) == 1:
                raw = match.group(1)
            else:
                raw = "".join(group or "" for group in match.groups())
            name = raw.replace("与", "").replace("和", "").replace("及", "").replace("的", "").strip(" 的。；，、")
            if any(name.endswith(k) for k in ["关联关系", "匹配关系", "映射关系", "绑定关系"]):
                return name
        return ""

    def _relation_data_name(self, l3: str) -> str:
        name = l3.replace("管理", "").replace("维护", "").strip() or l3
        if not name:
            return "业务关联关系"
        if name.endswith("关系"):
            return name
        if name.endswith("关联"):
            return f"{name}关系"
        return f"{name}关联关系"

    def _dedupe_data_functions(
        self,
        data_functions: list[tuple[str, str, str]],
    ) -> list[tuple[str, str, str]]:
        result: list[tuple[str, str, str]] = []
        seen: set[tuple[str, str]] = set()
        for name, fpa_type, reason in data_functions:
            key = (name, fpa_type)
            if not name or key in seen:
                continue
            seen.add(key)
            result.append((name, fpa_type, reason))
        return result

    def _transaction_name(self, name: str) -> str:
        return name.replace("-逻辑处理开发", "").replace("-接口处理开发", "").replace("-界面开发", "").strip()


@dataclass(frozen=True)
class UiApiMappingProfile(CustomRulesProfile):
    """界面接口映射口径。"""

    name: str = "ui_api_mapping"
    version: str = "1"
    description: str = "界面接口映射口径：每个功能过程生成界面开发和接口开发行，显式接口/后端调用单独补充。"
    core_rules: str = UI_API_MAPPING_CORE_RULES

    def agent_review_profile_kind(self) -> str:
        return "ui_api_mapping"

    def infer_type(self, name: str, desc: str = "") -> tuple[str, str]:
        if "界面开发" in name:
            return "EI", "功能过程界面开发行固定按 EI。"
        return "ILF", "功能过程接口开发或明确接口/后端调用行固定按 ILF。"

    def fallback_rows_for_l3(
        self,
        group: dict[str, object],
        meta: dict[str, str],
        start_seq: int = 1,
    ) -> list[dict[str, object]]:
        subsystem = meta.get("子系统（模块）", "")
        asset = meta.get("资产标识", "")
        tag = group_tag(group)
        processes = group.get("processes", [])
        process_list = processes if isinstance(processes, list) else []
        rows: list[dict[str, object]] = []
        seq = start_seq

        explicit_rows: dict[str, dict[str, object]] = {}
        default_point_names: set[str] = set()
        for p in process_list:
            if not isinstance(p, dict):
                continue
            raw_name = str(p.get("name", "") or "").strip()
            desc = str(p.get("desc", "") or "").strip()
            if not raw_name:
                continue
            status = str(p.get("type", "") or module_change_status(process_list))
            for suffix, fpa_type, reason in (
                ("界面开发", "EI", "功能过程默认生成 1 条界面开发行。"),
                ("接口开发", "ILF", "功能过程默认生成 1 条接口开发行。"),
            ):
                point_name = f"{tag}-{raw_name}-{suffix}"
                warning = ""
                if point_name in default_point_names:
                    warning = f"{point_name} ui_api_mapping 功能过程默认行同名，已保留并提示人工审阅。"
                default_point_names.add(point_name)
                rows.append({
                    "序号": seq,
                    "子系统(模块)": subsystem,
                    "资产标识": asset,
                    "新增/修改功能点": point_name,
                    "类型": fpa_type,
                    "计算依据归类": "",
                    "计算依据说明": f"{point_name}，来源功能过程：{desc or raw_name}",
                    "变更状态": status,
                    "调整值": adjust_value_for_type(fpa_type),
                    "要素数量": 1,
                    "生成方式": "fallback",
                    "类型理由": reason,
                    "源功能过程": raw_name,
                    "后处理警告": warning,
                })
                seq += 1

            for explicit_name in self._explicit_backend_interactions(raw_name, desc):
                point_name = f"{tag}-{explicit_name}"
                existing = explicit_rows.get(point_name)
                if existing is not None:
                    existing_sources = str(existing.get("源功能过程", "") or "")
                    if raw_name and raw_name not in existing_sources.split("、"):
                        existing["源功能过程"] = "、".join([part for part in [existing_sources, raw_name] if part])
                    continue
                row = {
                    "序号": seq,
                    "子系统(模块)": subsystem,
                    "资产标识": asset,
                    "新增/修改功能点": point_name,
                    "类型": "ILF",
                    "计算依据归类": "",
                    "计算依据说明": f"{point_name}，来源功能过程：{desc or raw_name}",
                    "变更状态": status,
                    "调整值": adjust_value_for_type("ILF"),
                    "要素数量": 1,
                    "生成方式": "fallback",
                    "类型理由": "输入材料明确出现接口、服务、调用或同步等后端交互，按明确接口/后端调用行固定 ILF。",
                    "源功能过程": raw_name,
                    "后处理警告": "",
                }
                explicit_rows[point_name] = row
                rows.append(row)
                seq += 1
        return _structure_fallback_explanations(group, rows)

    def _explicit_backend_interactions(self, name: str, desc: str) -> list[str]:
        text = f"{name}，{desc}"
        trigger_pattern = r"(?:接口|服务|调用|请求|对接|同步|外部系统|第三方|API)"
        if not re.search(trigger_pattern, text, re.IGNORECASE):
            return []
        candidates: list[str] = []
        primary_patterns = [
            r"调用\s*([^，。；、]{1,32}(?:接口|服务|API))",
            r"请求\s*([^，。；、]{1,32}(?:接口|服务|API))",
            r"对接\s*([^，。；、]{1,32}(?:平台|系统|接口|服务|API))",
            r"([^，。；、]{1,32}(?:接口|服务|API))",
        ]
        for pattern in primary_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group(1).strip(" 的。；，、")
                value = re.sub(r"^(?:调用|请求|对接)\s*", "", value).strip(" 的。；，、")
                if value and value not in candidates:
                    candidates.append(value)
        if candidates:
            return candidates
        for match in re.finditer(r"同步\s*([^，。；、]{1,32}(?:信息|数据|档案|记录)?)", text, re.IGNORECASE):
            value = match.group(1).strip(" 的。；，、")
            if value and value not in candidates:
                candidates.append(value)
        if candidates:
            return candidates
        phrase = re.split(r"[，。；、]", text, maxsplit=1)[0].strip()
        return [phrase] if phrase else []


UNIFIED_UI_PROFILE = CustomRulesProfile()
CUSTOM_RULES_PROFILE = UNIFIED_UI_PROFILE
STRICT_FPA_PROFILE = StrictFpaProfile()
UI_API_MAPPING_PROFILE = UiApiMappingProfile()
FPA_PROFILES = {
    UNIFIED_UI_PROFILE.name: UNIFIED_UI_PROFILE,
    STRICT_FPA_PROFILE.name: STRICT_FPA_PROFILE,
    UI_API_MAPPING_PROFILE.name: UI_API_MAPPING_PROFILE,
}


def _profile_from_kind(profile_name: str, kind: str) -> CustomRulesProfile:
    if kind == "strict_fpa":
        return StrictFpaProfile(name=profile_name)
    if kind == "unified_ui":
        return CustomRulesProfile(name=profile_name)
    if kind == "ui_api_mapping":
        return UiApiMappingProfile(name=profile_name)
    raise ValueError(f"未知 FPA profile kind: {kind}")


def get_fpa_profile(name: str = "unified_ui") -> CustomRulesProfile:
    profile_name = (name or "unified_ui").strip()
    profile = FPA_PROFILES.get(profile_name)
    if profile is not None:
        return profile
    try:
        from ai_gen_reimbursement_docs.config_utils import load_fpa_profile_kind
        return _profile_from_kind(profile_name, load_fpa_profile_kind(profile_name))
    except Exception as exc:
        raise ValueError(f"未知 FPA profile: {name}") from exc


def resolve_fpa_strategy(profile_name: str = "", strategy: str = "") -> str:
    """解析 FPA 执行策略。空值使用 profile 默认策略。"""
    profile_key = (profile_name or "unified_ui").strip()
    value = (strategy or "").strip()
    if not value:
        from ai_gen_reimbursement_docs.config_utils import load_fpa_strategy
        value = load_fpa_strategy(profile_key)
    if value not in VALID_FPA_STRATEGIES:
        raise ValueError(f"未知 FPA strategy: {strategy}")
    return value


def resolve_fpa_rule_set(profile_name: str = "", rule_set: str = "") -> str:
    """解析 FPA 规则集名称。空值使用 profile 默认规则集。"""
    profile_key = (profile_name or "unified_ui").strip()
    value = (rule_set or "").strip()
    if not value:
        from ai_gen_reimbursement_docs.config_utils import load_fpa_rule_set
        value = load_fpa_rule_set(profile_key)
    return value


def resolve_fpa_execution_config(
    profile_name: str = "",
    strategy: str = "",
    rule_set: str = "",
) -> FpaExecutionConfig:
    """统一解析一次 FPA 执行配置。"""
    profile = get_fpa_profile(profile_name)
    resolved_rule_set = resolve_fpa_rule_set(profile.name, rule_set)
    rule_set_config = resolve_fpa_rule_set_config(resolved_rule_set)
    return FpaExecutionConfig(
        profile=profile,
        strategy=resolve_fpa_strategy(profile.name, strategy),
        rule_set=resolved_rule_set,
        rule_set_config=rule_set_config,
    )
