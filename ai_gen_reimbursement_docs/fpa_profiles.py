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

CUSTOM_RULES_CORE_RULES = "请在 fpa_config.yaml 的 profiles.custom_rules.core_rules 配置 custom_rules 核心口径。"
STRICT_FPA_CORE_RULES = "请在 fpa_config.yaml 的 profiles.strict_fpa.core_rules 配置 strict_fpa 核心口径。"


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


def group_tag(group: dict[str, object]) -> str:
    return (
        f"【{group.get('client_type', '')}】"
        f"{group.get('l1', '')}-{group.get('l2', '')}-{group.get('l3', '')}"
    )


def adjust_value_for_type(fpa_type: str) -> int:
    return 2 if fpa_type == "EI" else 1


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


def _prompt_payload(
    group: dict[str, object],
    domain_context: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "module": {
            "client_type": group.get("client_type", ""),
            "l1": group.get("l1", ""),
            "l2": group.get("l2", ""),
            "l3": group.get("l3", ""),
            "l3_desc": group.get("l3_desc", ""),
        },
        "processes": group.get("processes", []),
        "domain_context": domain_context or {},
    }


def _numbered_judgement_rules(judgement_rules: list[str]) -> str:
    return "\n".join(f"{i}) {r}" for i, r in enumerate(judgement_rules, 1)) or "（无）"


def _render_configured_fpa_prompt(
    profile_name: str,
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
        "payload_json": json.dumps(_prompt_payload(group, domain_context), ensure_ascii=False, indent=2),
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
    resolving: set[str] = set()

    def _resolve(name: str) -> FpaRuleSetConfig:
        if name in resolving:
            raise ValueError(f"FPA rule_set 继承出现循环: {name}")
        resolving.add(name)
        try:
            current = configured.get(name)
            if current is None:
                raise ValueError(f"未知 FPA rule_set: {name}")
            if current.extends:
                parent = _resolve(current.extends)
                current = _merge_rule_sets(parent, current)
            return current
        finally:
            resolving.remove(name)

    return _resolve(rule_set)


def current_fpa_rule_set_config() -> FpaRuleSetConfig | None:
    return _CURRENT_RULE_SET_CONFIG.get()


def set_current_fpa_rule_set_config(config: FpaRuleSetConfig):
    return _CURRENT_RULE_SET_CONFIG.set(config)


def reset_current_fpa_rule_set_config(token) -> None:
    _CURRENT_RULE_SET_CONFIG.reset(token)


@dataclass(frozen=True)
class CustomRulesProfile:
    """用户自定义规则口径。"""

    name: str = "custom_rules"
    version: str = "1"
    description: str = "用户自定义规则口径：三级模块合并界面能力，非界面逻辑按动作拆分。"
    core_rules: str = CUSTOM_RULES_CORE_RULES

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
            return rows
        for p in process_list:
            if not isinstance(p, dict):
                continue
            name = str(p.get("name", "") or "").strip()
            desc = str(p.get("desc", "") or "").strip()
            if not name:
                continue
            point_name = self.logic_point_name(name, desc)
            fpa_type, reason = self.infer_type(point_name, desc)
            rows.append({
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
            })
            seq += 1
        return rows

    def build_prompt(
        self,
        group: dict[str, object],
        judgement_rules: list[str],
        domain_context: dict[str, object] | None = None,
    ) -> str:
        return _render_configured_fpa_prompt(self.name, self.core_rules, group, judgement_rules, domain_context)

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

    def infer_type(self, name: str, desc: str = "") -> tuple[str, str]:
        text = f"{name} {desc}"
        type_mapping = self._configured_type_mapping(text)
        if type_mapping:
            return type_mapping
        if self._looks_like_external_data_function_name(name) and self._is_external_data_group(text):
            return "EIF", "明确引用外部系统维护的数据组，按 EIF。"
        name_action = self._explicit_transaction_type(name)
        if name_action:
            return name_action
        if self._is_external_data_group(text):
            return "EIF", "明确引用外部系统维护的数据组，按 EIF。"
        internal_rule = self._matching_internal_data_rule(text)
        if internal_rule is not None:
            return "ILF", internal_rule.reason or "命中 rule_set 内部数据组规则，按 ILF。"
        if self._looks_like_data_group(name, desc):
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
        action_keywords = self._configured_transaction_keywords()
        return (
            any(noun in name for noun in EXTERNAL_DATA_GROUP_NOUNS)
            and not any(action in name for action in action_keywords)
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
        type_mapping = self._configured_type_mapping(text)
        if type_mapping:
            return type_mapping[0]
        name_action = self._explicit_transaction_type(name)
        if name_action:
            return name_action[0]
        if self._looks_like_external_data_function_name(name) and self._is_external_data_group(text):
            return "EIF"
        if self._is_external_data_group(text) and self._looks_like_external_data_function_name(name):
            return "EIF"
        if self._matching_internal_data_rule(text) is not None:
            return "ILF"
        if self._looks_like_data_group(name, desc):
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
            rows.append({
                "序号": seq,
                "子系统(模块)": subsystem,
                "资产标识": asset,
                "新增/修改功能点": data_name,
                "类型": data_type,
                "计算依据归类": "",
                "计算依据说明": f"{data_name}，作为该三级模块涉及的逻辑数据组。",
                "变更状态": module_change_status(process_list),
                "调整值": adjust_value_for_type(data_type),
                "要素数量": 1,
                "生成方式": "fallback",
                "类型理由": data_reason,
                "源功能过程": "、".join(str(p.get("name", "")) for p in process_list if isinstance(p, dict)),
                "后处理警告": "",
            })
            seq += 1

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
            rows.append({
                "序号": seq,
                "子系统(模块)": subsystem,
                "资产标识": asset,
                "新增/修改功能点": point_name,
                "类型": fpa_type,
                "计算依据归类": "",
                "计算依据说明": f"{point_name}，具体为以下：\n1、{desc or raw_name}",
                "变更状态": str(p.get("type", "") or module_change_status(process_list)),
                "调整值": adjust_value_for_type(fpa_type),
                "要素数量": 1,
                "生成方式": "fallback",
                "类型理由": reason,
                "源功能过程": raw_name,
                "后处理警告": "",
            })
            seq += 1
        return rows

    def build_prompt(
        self,
        group: dict[str, object],
        judgement_rules: list[str],
        domain_context: dict[str, object] | None = None,
    ) -> str:
        return _render_configured_fpa_prompt(self.name, self.core_rules, group, judgement_rules, domain_context)

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
        text = f"{name} {desc}"
        if (
            any(k in text for k in EXTERNAL_MAINTAINED_HINTS)
            or re.search(r"(?:外部应用|外部系统|第三方系统|外部|第三方)[^，。；、\s]{0,16}(?:维护|提供)", text)
        ) and not self._has_internal_data_function(text):
            return False
        if any(k in name for k in ["信息", "数据组", "主数据", "名单", "关系", "配置", "记录", "模板"]):
            return not any(k in name for k in ["查询", "查看", "详情", "新增", "添加", "修改", "编辑", "删除", "导入", "导出"])
        return "维护" in text and not any(k in name for k in ["查询", "查看", "新增", "添加", "修改", "编辑", "删除"])

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
        if any(k in name for k in ["信息", "数据组", "主数据", "名单", "关系", "配置", "记录", "模板"]):
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
        return any(k in text for k in [
            "本系统维护", "本系统保存", "本系统继续维护",
            "维护本系统", "记录本系统",
        ])

    def _external_data_group_rules(self) -> list[ExternalDataGroupRule]:
        current_rule_set = current_fpa_rule_set_config()
        return list(current_rule_set.external_data_rules) if current_rule_set is not None else []

    def _configured_keyword_rules(self) -> tuple[KeywordTypeRule, ...]:
        return super()._configured_keyword_rules()

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


CUSTOM_RULES_PROFILE = CustomRulesProfile()
STRICT_FPA_PROFILE = StrictFpaProfile()
FPA_PROFILES = {
    CUSTOM_RULES_PROFILE.name: CUSTOM_RULES_PROFILE,
    STRICT_FPA_PROFILE.name: STRICT_FPA_PROFILE,
}


def get_fpa_profile(name: str = "custom_rules") -> CustomRulesProfile:
    profile = FPA_PROFILES.get(name or CUSTOM_RULES_PROFILE.name)
    if profile is not None:
        return profile
    raise ValueError(f"未知 FPA profile: {name}")


def resolve_fpa_strategy(profile_name: str = "", strategy: str = "") -> str:
    """解析 FPA 执行策略。空值使用 profile 默认策略。"""
    profile_key = (profile_name or CUSTOM_RULES_PROFILE.name).strip()
    value = (strategy or "").strip()
    if not value:
        from ai_gen_reimbursement_docs.config_utils import load_fpa_strategy
        value = load_fpa_strategy(profile_key)
    if value not in VALID_FPA_STRATEGIES:
        raise ValueError(f"未知 FPA strategy: {strategy}")
    return value


def resolve_fpa_rule_set(profile_name: str = "", rule_set: str = "") -> str:
    """解析 FPA 规则集名称。空值使用 profile 默认规则集。"""
    profile_key = (profile_name or CUSTOM_RULES_PROFILE.name).strip()
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
