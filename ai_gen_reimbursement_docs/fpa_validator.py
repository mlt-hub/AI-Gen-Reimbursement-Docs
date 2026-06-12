"""Structured validation for generated FPA rows.

The validator is intentionally conservative: it reports high-confidence
project口径 violations as warnings/retry hints, but does not rewrite rows.
"""

from dataclasses import dataclass
import re


VALID_FPA_TYPES = {"EI", "EQ", "EO", "ILF", "EIF"}
QUERY_KEYWORDS = ("查询", "搜索", "检索", "列表", "查看", "详情")
MAINTENANCE_KEYWORDS = ("新增", "添加", "修改", "编辑", "删除", "保存", "维护", "启用", "停用")
ORDINARY_SERVICE_HINTS = (
    "校验", "认证", "鉴权", "权限", "手机号", "短信", "支付", "OCR", "消息推送", "发送",
)
EXTERNAL_DATA_EVIDENCE = (
    "外部系统维护", "外部应用维护", "第三方系统维护", "外部维护", "本系统不维护",
    "维护的主数据", "维护的数据组", "维护的档案", "维护的记录",
)
EXPLANATION_REQUIRED_LABELS = ("来源场景：", "业务数据：", "业务规则：", "计算说明：")


@dataclass(frozen=True)
class FpaValidationIssue:
    """A non-destructive validation issue for a generated FPA row set."""

    code: str
    message: str
    row_index: int | None = None
    retryable: bool = False
    severity: str = "warning"


def validate_fpa_rows(
    *,
    group: dict[str, object],
    rows: list[dict[str, object]],
) -> list[FpaValidationIssue]:
    """Validate normalized FPA rows against stable gen-fpa project口径."""
    issues: list[FpaValidationIssue] = []
    id_to_process = _processes_by_id(group)
    valid_ids = set(id_to_process)

    for index, row in enumerate(rows):
        name = str(row.get("新增/修改功能点", "") or row.get("name", "") or "").strip()
        fpa_type = str(row.get("类型", "") or row.get("type", "") or "").strip().upper()
        source_ids = _source_process_ids(row)
        source_text = _row_source_text(row, id_to_process)
        evidence = " ".join([
            name,
            str(row.get("类型理由", "") or row.get("type_reason", "")),
            str(row.get("计算依据说明", "") or row.get("explanation", "")),
            source_text,
        ])

        if fpa_type not in VALID_FPA_TYPES:
            issues.append(FpaValidationIssue(
                code="validator.invalid_type",
                message=f"{name or f'第 {index + 1} 行'} FPA 类型非法: {fpa_type or '空'}",
                row_index=index,
                retryable=True,
            ))

        unknown_ids = sorted(source_ids - valid_ids)
        if unknown_ids:
            issues.append(FpaValidationIssue(
                code="validator.unknown_source_process_ids",
                message=f"{name} source_process_ids 越界: {'、'.join(unknown_ids)}",
                row_index=index,
                retryable=True,
            ))

        if (
            fpa_type == "EI"
            and _looks_query_only(evidence)
            and not _looks_maintenance(evidence)
            and not _looks_ui_workload_row(name)
        ):
            issues.append(FpaValidationIssue(
                code="validator.query_as_ei",
                message=f"{name} 疑似查询类流程被判为 EI，应按只读查询优先判为 EQ",
                row_index=index,
                retryable=True,
            ))

        if fpa_type == "EIF" and _looks_ordinary_service(evidence) and not _has_external_data_evidence(evidence):
            issues.append(FpaValidationIssue(
                code="validator.ordinary_service_as_eif",
                message=f"{name} 疑似将普通校验/外部服务调用识别为 EIF，缺少外部维护数据组证据",
                row_index=index,
                retryable=True,
            ))

        missing_labels = [
            label.rstrip("：")
            for label in EXPLANATION_REQUIRED_LABELS
            if label not in str(row.get("计算依据说明", "") or row.get("explanation", ""))
        ]
        if missing_labels:
            issues.append(FpaValidationIssue(
                code="validator.explanation_structure",
                message=f"{name} 计算依据说明格式不完整，缺少结构化项: {'、'.join(missing_labels)}",
                row_index=index,
                retryable=False,
            ))

    issues.extend(_split_transaction_issues(group=group, rows=rows))
    return issues


def retryable_validation_issues(issues: list[FpaValidationIssue]) -> list[FpaValidationIssue]:
    return [issue for issue in issues if issue.retryable]


def validation_feedback(issues: list[FpaValidationIssue], *, limit: int = 6) -> str:
    """Render compact feedback to send back to the model for one retry."""
    selected = retryable_validation_issues(issues)[:limit]
    if not selected:
        return ""
    lines = [
        "上一次 FPA JSON 输出未通过项目口径校验，请只修正 rows JSON，不要解释。",
        "必须修正以下问题：",
    ]
    lines.extend(f"- {issue.message}" for issue in selected)
    lines.extend([
        "硬约束：查询/列表/搜索/查看且不改变数据的流程不得判 EI。",
        "硬约束：普通校验、认证、权限、手机号检查、短信/支付/OCR 等服务调用不得生成 EIF，除非输入明确说明外部系统维护的数据组被本系统读取。",
        "硬约束：source_process_ids 必须来自当前输入 processes.process_id。",
    ])
    return "\n".join(lines)


def _processes_by_id(group: dict[str, object]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    processes = group.get("processes", [])
    if not isinstance(processes, list):
        return result
    for process in processes:
        if not isinstance(process, dict):
            continue
        process_id = str(process.get("process_id", "") or "").strip()
        if not process_id:
            continue
        result[process_id] = {
            "name": str(process.get("process_name", "") or process.get("name", "") or "").strip(),
            "description": str(process.get("description", "") or process.get("desc", "") or "").strip(),
        }
    return result


def _source_process_ids(row: dict[str, object]) -> set[str]:
    raw = row.get("source_process_ids", [])
    if isinstance(raw, list):
        return {str(item).strip() for item in raw if str(item).strip()}
    if isinstance(raw, str):
        return {item.strip() for item in re.split(r"[、,，;；\s]+", raw) if item.strip()}
    return set()


def _row_source_text(row: dict[str, object], id_to_process: dict[str, dict[str, str]]) -> str:
    parts: list[str] = []
    for source_id in _source_process_ids(row):
        process = id_to_process.get(source_id)
        if process:
            parts.extend([process["name"], process["description"]])
    parts.append(str(row.get("源功能过程", "") or ""))
    return " ".join(part for part in parts if part)


def _looks_query_only(text: str) -> bool:
    return any(keyword in text for keyword in QUERY_KEYWORDS)


def _looks_ui_workload_row(name: str) -> bool:
    return "界面开发" in name


def _looks_maintenance(text: str) -> bool:
    return any(keyword in text for keyword in MAINTENANCE_KEYWORDS)


def _looks_ordinary_service(text: str) -> bool:
    return any(hint in text for hint in ORDINARY_SERVICE_HINTS)


def _has_external_data_evidence(text: str) -> bool:
    return any(hint in text for hint in EXTERNAL_DATA_EVIDENCE)


def _split_transaction_issues(
    *,
    group: dict[str, object],
    rows: list[dict[str, object]],
) -> list[FpaValidationIssue]:
    """Detect obvious AI output that counted one process as one function point."""
    issues: list[FpaValidationIssue] = []
    ei_rows = [
        (idx, row) for idx, row in enumerate(rows)
        if str(row.get("类型", "") or "").strip().upper() == "EI"
    ]
    eq_rows = [
        (idx, row) for idx, row in enumerate(rows)
        if str(row.get("类型", "") or "").strip().upper() == "EQ"
    ]
    if len(ei_rows) >= 2 and _same_module_business_object(group, [row for _, row in ei_rows]):
        maintenance_buckets: dict[str, list[str]] = {}
        for _, row in ei_rows:
            text = str(row.get("新增/修改功能点", "") or "") + str(row.get("源功能过程", "") or "")
            if not _looks_maintenance(text):
                continue
            key = _maintenance_object_key(row)
            maintenance_buckets.setdefault(key, []).append(str(row.get("新增/修改功能点", "") or ""))
        for maintenance_names in maintenance_buckets.values():
            if len(maintenance_names) >= 2:
                issues.append(FpaValidationIssue(
                    code="validator.split_crud_ei",
                    message="同一业务对象的多个维护动作疑似被拆成多个 EI，应合并为一个维护类 EI: "
                    + "、".join(maintenance_names[:5]),
                    retryable=True,
                ))
                break
    if len(eq_rows) >= 2 and _same_module_business_object(group, [row for _, row in eq_rows]):
        query_names = [
            str(row.get("新增/修改功能点", "") or "")
            for _, row in eq_rows
            if _looks_query_only(str(row.get("新增/修改功能点", "") or "") + str(row.get("源功能过程", "") or ""))
        ]
        if len(query_names) >= 2:
            issues.append(FpaValidationIssue(
                code="validator.split_query_eq",
                message="同一列表/搜索场景的多个查询动作疑似被拆成多个 EQ，应合并为一个查询类 EQ: "
                + "、".join(query_names[:5]),
                retryable=True,
            ))
    return issues


def _same_module_business_object(group: dict[str, object], rows: list[dict[str, object]]) -> bool:
    l3 = str(group.get("l3", "") or "").replace("管理", "").replace("维护", "").strip()
    if not l3:
        return True
    hits = 0
    for row in rows:
        text = str(row.get("新增/修改功能点", "") or "") + str(row.get("源功能过程", "") or "")
        if l3 in text or l3[: max(2, len(l3) - 2)] in text:
            hits += 1
    return hits >= 2


def _maintenance_object_key(row: dict[str, object]) -> str:
    text = str(row.get("新增/修改功能点", "") or "")
    if "-" in text:
        text = text.rsplit("-", 1)[-1]
    source = str(row.get("源功能过程", "") or "")
    source_parts = [part.strip() for part in re.split(r"[、,，;；\s]+", source) if part.strip()]
    source_keys = [_clean_maintenance_object(part) for part in source_parts]
    source_keys = [key for key in source_keys if key]
    if source_keys and len(set(source_keys)) == 1:
        return source_keys[0]
    return _clean_maintenance_object(text) or text


def _clean_maintenance_object(text: str) -> str:
    value = str(text or "").strip()
    if "-" in value:
        value = value.rsplit("-", 1)[-1]
    value = re.sub(r"^(新增|添加|新建|创建|录入|编辑|修改|更新|删除|移除|保存|维护|启用|停用)", "", value)
    value = re.sub(r"(维护|新增|添加|编辑|修改|删除|保存|启用|停用)$", "", value)
    return value.strip()
