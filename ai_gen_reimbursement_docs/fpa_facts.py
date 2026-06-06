"""Business-fact extraction for FPA generation.

This module creates a small, deterministic JSON layer between raw
`processes` and final FPA rows. It is not the final FPA judgement; it is a
stable intermediate shape that later agent steps can consume and validate.
"""

from dataclasses import asdict, dataclass
import re


QUERY_KEYWORDS = ("查询", "搜索", "检索", "列表", "查看", "详情", "浏览", "读取")
CREATE_KEYWORDS = ("新增", "添加", "新建", "创建", "录入")
UPDATE_KEYWORDS = ("编辑", "修改", "更新", "调整", "保存", "维护", "配置", "设置")
DELETE_KEYWORDS = ("删除", "移除", "作废")
ENABLE_KEYWORDS = ("启用", "停用", "上架", "下架", "生效", "失效")
OUTPUT_KEYWORDS = ("导出", "报表", "下载", "统计", "汇总", "生成文件")
EXTERNAL_SERVICE_HINTS = ("调用", "校验", "认证", "鉴权", "权限", "短信", "支付", "OCR", "消息推送")
EXTERNAL_DATA_EVIDENCE = (
    "外部系统维护", "外部应用维护", "第三方系统维护", "外部维护",
    "本系统不维护", "维护的主数据", "维护的数据组", "维护的档案", "维护的记录",
)
LOCAL_CHANGE_HINTS = (
    "新增", "添加", "新建", "创建", "录入", "编辑", "修改", "更新", "调整",
    "保存", "写入", "删除", "移除", "启用", "停用", "关联到", "保存到",
    "维护本系统", "本系统维护",
)


@dataclass(frozen=True)
class FpaProcessFact:
    process_id: str
    process_name: str
    input_type: str
    operation: str
    target_data_group: str
    query_only: bool
    changes_internal_data: bool
    produces_external_output: bool
    ordinary_external_service: bool
    external_data_group_evidence: str
    confidence: str
    evidence: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def extract_fpa_process_facts(group: dict[str, object]) -> list[dict[str, object]]:
    """Extract deterministic business facts from a grouped L3 module."""
    processes = group.get("processes", [])
    if not isinstance(processes, list):
        return []
    facts: list[dict[str, object]] = []
    module_data_group = _module_data_group_name(str(group.get("l3", "") or ""))
    module_text = str(group.get("l3_desc", "") or "")
    for process in processes:
        if not isinstance(process, dict):
            continue
        fact = _extract_process_fact(process, module_data_group, module_text)
        facts.append(fact.to_dict())
    return facts


def _extract_process_fact(
    process: dict[str, object],
    module_data_group: str,
    module_text: str = "",
) -> FpaProcessFact:
    process_id = str(process.get("process_id", "") or "").strip()
    name = str(process.get("process_name", "") or process.get("name", "") or "").strip()
    desc = str(process.get("description", "") or process.get("desc", "") or "").strip()
    input_type = str(process.get("type", "") or "").strip()
    text = f"{name}。{desc}"
    evidence_text = f"{text}。{module_text}" if module_text else text
    operation, operation_evidence = _operation(text)
    external_evidence = _external_data_evidence(evidence_text)
    query_only = operation == "query" and not _has_any(text, LOCAL_CHANGE_HINTS)
    produces_output = operation == "output"
    ordinary_service = _has_any(text, EXTERNAL_SERVICE_HINTS) and not external_evidence
    changes_internal = operation in {"create", "update", "delete", "enable_disable", "maintain"}
    evidence = [item for item in [operation_evidence, external_evidence] if item]
    if input_type and input_type not in evidence:
        evidence.append(f"input_type={input_type}")
    return FpaProcessFact(
        process_id=process_id,
        process_name=name,
        input_type=input_type,
        operation=operation,
        target_data_group=_target_data_group(evidence_text if external_evidence else text, module_data_group),
        query_only=query_only,
        changes_internal_data=changes_internal,
        produces_external_output=produces_output,
        ordinary_external_service=ordinary_service,
        external_data_group_evidence=external_evidence,
        confidence="high" if operation_evidence else "medium",
        evidence=evidence,
    )


def _operation(text: str) -> tuple[str, str]:
    for operation, keywords in (
        ("output", OUTPUT_KEYWORDS),
        ("query", QUERY_KEYWORDS),
        ("delete", DELETE_KEYWORDS),
        ("create", CREATE_KEYWORDS),
        ("update", UPDATE_KEYWORDS),
        ("enable_disable", ENABLE_KEYWORDS),
    ):
        keyword = _first_keyword(text, keywords)
        if keyword:
            return operation, f"命中关键词：{keyword}"
    return "maintain", ""


def _target_data_group(text: str, fallback: str) -> str:
    external = _extract_external_data_name(text)
    if external:
        return external
    admin_match = re.search(r"(?:新增|添加|删除|移除|编辑|修改|查询|查看)([^，。；、\s]{0,24}管理员)", text)
    if admin_match:
        value = _clean_data_name(admin_match.group(1))
        if value:
            return value
    patterns = [
        r"(?:新增|添加|新建|创建|录入|编辑|修改|删除|查询|搜索|查看|维护|保存)([^，。；、\s]{2,24}?)(?:信息|数据|列表|详情|记录|档案|关系|账号|管理员)?(?:，|。|；|、|$)",
        r"(?:保存|维护|读取|展示)([^，。；、\s]{2,24}(?:信息|数据|记录|档案|关系|账号|主数据))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = _clean_data_name(match.group(1))
            if value:
                return value
    return fallback or "业务数据"


def _module_data_group_name(l3: str) -> str:
    name = l3.replace("管理", "").replace("维护", "").strip()
    return name or l3 or "业务数据"


def _external_data_evidence(text: str) -> str:
    for hint in EXTERNAL_DATA_EVIDENCE:
        if hint in text:
            name = _extract_external_data_name(text)
            return f"{hint}: {name}" if name else hint
    return ""


def _extract_external_data_name(text: str) -> str:
    patterns = [
        r"(?:读取|引用|选择|关联|查看)([^，。；、\s]{2,24}(?:主数据|数据组|档案|信息|记录|账号|单据|订单))",
        r"(?:外部系统|外部应用|第三方系统|外部|第三方|CRM|ERP|主数据平台|统一用户中心)[^，。；、\s]{0,16}(?:维护|提供)的?([^，。；、\s]{2,24}(?:主数据|数据组|档案|信息|记录|账号|单据|订单))",
        r"([^，。；、\s]{2,24}(?:主数据|数据组|档案|信息|记录|账号|单据|订单))(?:由|为)?(?:外部系统|外部应用|第三方系统|外部|第三方|CRM|ERP|主数据平台|统一用户中心)[^，。；、\s]{0,12}(?:维护|提供)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _clean_data_name(match.group(1))
    return ""


def _clean_data_name(value: str) -> str:
    text = str(value or "").strip(" 的。；，、")
    text = re.sub(r"^统一用户中心[^，。；、\s]{0,12}维护的[^，。；、\s]*账号$", "统一用户中心账号", text)
    text = re.sub(r"^主数据平台[^，。；、\s]{0,12}维护的([^，。；、\s]*主数据)$", r"\1", text)
    text = re.sub(r"^(?:指定|当前|存量|有效|已保存的|本系统|外部系统|外部应用|第三方系统)", "", text)
    text = re.split(r"(?:中选择|中查看|中读取|并|及|和|，|。|；|、)", text, maxsplit=1)[0]
    return text.strip(" 的。；，、")


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _first_keyword(text: str, keywords: tuple[str, ...]) -> str:
    return next((keyword for keyword in keywords if keyword in text), "")
