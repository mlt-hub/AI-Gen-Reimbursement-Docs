"""FPA 规划口径策略。

每套 profile 自己提供 prompt、兜底拆分、类型推断和冲突判断，
避免把多套口径分支散落到 gen_fpa.py 主流程中。
"""

from dataclasses import dataclass
import re
from string import Template


CURRENT_PROJECT_CORE_RULES = """
FPA 核心口径：
1. 拆分先按业务能力粒度，不按按钮、弹窗、数据库表、字段或技术实现拆分。
2. 同一三级模块中的列表、查询条件、按钮、新增/编辑弹窗、状态切换等界面能力默认合并为 1 条界面开发行。
3. 只有独立页面、独立业务对象、独立业务流程或独立用户端，才允许拆成多条界面开发行；多条界面行必须给出 split_reason。
4. 非界面类后端逻辑按功能动作拆分，一行表示一个业务动作或数据处理能力。
5. 新增表、保存表、字段维护等不要单独生成 FPA 行，应归属到对应功能动作中。
6. 类型可使用 EI、ILF、EQ、EO、EIF：界面交互通常为 EI；内部数据维护通常为 ILF；查询读取通常为 EQ；导出/报表输出通常为 EO；EIF 仅用于引用其他应用维护的数据组。
7. 计算依据归类只能从给定判定原则列表中选择，不要自造分类。
""".strip()


STRICT_FPA_CORE_RULES = """
严格 FPA 核心口径：
1. 按标准 FPA 的数据功能和事务功能拆分，不按开发工作项、页面、按钮、弹窗、接口或数据库表字段拆分。
2. 不生成“界面开发”“接口开发”“逻辑处理开发”等开发工作项行。
3. 本系统维护的逻辑数据组生成 ILF；外部系统维护、本系统引用的数据组生成 EIF。
4. 新增、修改、删除、保存、提交、审批、启用、停用、导入等进入或改变系统边界内数据的事务功能为 EI。
5. 查询、查看、详情、检索等无派生输出的读取事务功能为 EQ。
6. 导出、报表、下载文件、生成文件等有派生或格式化输出的事务功能为 EO。
7. 普通外部服务调用不等于 EIF；只有明确引用外部维护的数据组时才生成 EIF。
8. 计算依据归类只能从给定判定原则列表中选择，不要自造分类。
""".strip()


EXTERNAL_DATA_GROUP_NOUNS = [
    "数据组", "主数据", "基础数据", "档案", "信息", "记录", "账号", "账户", "单据", "客户",
    "人员", "组织", "机构",
]

EXTERNAL_MAINTAINED_HINTS = [
    "外部应用维护", "外部系统维护", "第三方系统维护", "外部维护", "外部应用提供",
    "外部系统提供", "第三方系统提供", "本系统不维护", "引用外部数据组",
]

STRICT_EO_ACTIONS = ("导出", "报表", "下载", "生成文件")
STRICT_EQ_ACTIONS = ("查询", "查看", "详情", "检索", "列表")
STRICT_EI_ACTIONS = (
    "新增", "添加", "修改", "编辑", "删除", "保存", "提交", "审批", "启用", "停用",
    "导入", "选择", "引用", "关联",
)
EXTERNAL_SERVICE_CALL_HINTS = ("外部接口", "外部服务", "调用", "平台发送", "网关", "服务上传")


@dataclass(frozen=True)
class ExternalDataGroupRule:
    """外部系统维护、本系统只引用的数据组识别规则。"""

    source_aliases: tuple[str, ...]
    data_name: str
    data_nouns: tuple[str, ...] = tuple(EXTERNAL_DATA_GROUP_NOUNS)

    def matches(self, text: str) -> bool:
        return any(alias in text for alias in self.source_aliases) and any(noun in text for noun in self.data_nouns)


DEFAULT_EXTERNAL_DATA_GROUP_RULES = [
    ExternalDataGroupRule(("统一用户中心", "用户中心"), "统一用户中心账号", ("账号", "账户", "人员", "组织", "机构", "信息")),
    ExternalDataGroupRule(("CRM", "客户关系管理系统"), "CRM客户档案", ("客户", "档案", "信息", "记录", "主数据")),
    ExternalDataGroupRule(("客户中心", "客户主数据平台"), "客户中心客户档案", ("客户", "档案", "信息", "记录", "主数据")),
    ExternalDataGroupRule(("财务核算系统",), "财务核算单据", ("单据", "报账", "凭证", "记录", "信息")),
    ExternalDataGroupRule(("财务系统",), "财务系统单据", ("单据", "报账", "凭证", "记录", "信息")),
    ExternalDataGroupRule(("ERP", "ERP系统"), "ERP业务单据", ("单据", "订单", "物料", "供应商", "记录", "信息")),
    ExternalDataGroupRule(("OA", "OA系统"), "OA流程单据", ("单据", "流程", "审批", "记录", "信息")),
    ExternalDataGroupRule(("主数据平台", "外部主数据"), "外部主数据", ("主数据", "基础数据", "数据组", "信息")),
]


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
    try:
        import json
        from ai_gen_reimbursement_docs.config_utils import load_fpa_user_prompt_template

        template = load_fpa_user_prompt_template(profile_name)
        if not template:
            return ""
        return Template(template).safe_substitute({
            "core_rules": core_rules,
            "judgement_rules": _numbered_judgement_rules(judgement_rules),
            "payload_json": json.dumps(_prompt_payload(group, domain_context), ensure_ascii=False, indent=2),
        })
    except Exception:
        return ""


@dataclass(frozen=True)
class CurrentProjectProfile:
    """当前报账模板口径。"""

    name: str = "current_project"
    version: str = "1"
    description: str = "当前报账模板口径：三级模块合并界面能力，非界面逻辑按动作拆分。"
    core_rules: str = CURRENT_PROJECT_CORE_RULES

    def infer_type(self, name: str, desc: str = "") -> tuple[str, str]:
        """按当前项目关键词规则给出类型兜底。"""
        text = f"{name} {desc}"
        if "界面开发" in text or "页面" in text:
            return "EI", "关键词命中界面/页面能力，按 EI 兜底。"
        if any(k in text for k in ["外部应用维护", "外部系统维护", "引用外部数据组", "统一用户中心", "外部主数据"]):
            return "EIF", "描述明确引用外部应用维护的数据组，按 EIF 兜底。"
        if any(k in text for k in ["导出", "报表输出", "生成文件", "下载模板", "下载文件"]) or ("下载" in text and "模板" in text):
            return "EO", "关键词命中导出/输出能力，按 EO 兜底。"
        if any(k in text for k in ["查询", "查看", "详情", "列表检索", "检索"]):
            return "EQ", "关键词命中查询/查看能力，按 EQ 兜底。"
        if "导入" in text:
            return "EI", "关键词命中导入能力，通常表示外部数据进入系统，按 EI 兜底。"
        if any(k in text for k in ["添加", "新增", "编辑", "修改", "删除", "维护", "保存", "启用", "停用", "更新"]):
            return "ILF", "关键词命中内部数据维护能力，按 ILF 兜底。"
        if "外部接口" in text or "外部数据" in text:
            return "ILF", "仅出现外部接口不足以判定 EIF，按 ILF 兜底。"
        return "ILF", "未命中明确类型关键词，按 ILF 兜底。"

    def has_obvious_conflict(self, name: str, desc: str, ai_type: str) -> bool:
        expected, _ = self.infer_type(name, desc)
        if "外部接口" in f"{name} {desc}" and expected == "ILF":
            return ai_type == "EIF"
        return expected != ai_type and any(
            k in f"{name} {desc}"
            for k in ["界面开发", "导出", "导入", "查询", "查看", "详情", "添加", "新增", "编辑", "删除", "维护", "保存"]
        )

    def logic_point_name(self, name: str, desc: str = "") -> str:
        text = f"{name} {desc}"
        if any(k in text for k in ["查询", "查看", "详情", "列表检索", "检索"]):
            return f"{name}-查询处理开发"
        if any(k in text for k in ["导出", "报表输出", "生成文件", "下载模板", "下载文件"]) or ("下载" in text and "模板" in text):
            return f"{name}-导出处理开发"
        if "导入" in text:
            return f"{name}-导入处理开发"
        return f"{name}-逻辑处理开发"

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

        ui_items = []
        for p in process_list:
            if not isinstance(p, dict):
                continue
            name = str(p.get("name", "") or "").strip()
            desc = str(p.get("desc", "") or "").strip()
            if name or desc:
                ui_items.append(desc or name)
        ui_detail = "\n".join(f"{i}、{item}" for i, item in enumerate(ui_items or ["完成三级模块页面交互能力"], 1))
        rows.append({
            "序号": seq,
            "子系统(模块)": subsystem,
            "资产标识": asset,
            "新增/修改功能点": f"{tag}-界面开发",
            "类型": "EI",
            "计算依据归类": "",
            "计算依据说明": f"{tag}-界面开发，具体为以下：\n{ui_detail}",
            "变更状态": module_change_status(process_list),
            "调整值": 2,
            "要素数量": 1,
            "生成方式": "fallback",
            "类型理由": "三级模块兜底合并界面能力。",
            "源功能过程": "、".join(str(p.get("name", "")) for p in process_list if isinstance(p, dict)),
            "后处理警告": "",
        })
        seq += 1

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
                "计算依据说明": f"{point_name}，具体为以下：\n1、{desc or name}",
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
        import json

        configured_prompt = _render_configured_fpa_prompt(self.name, self.core_rules, group, judgement_rules, domain_context)
        if configured_prompt:
            return configured_prompt
        numbered_rules = _numbered_judgement_rules(judgement_rules)
        payload = _prompt_payload(group, domain_context)
        return (
            f"{self.core_rules}\n\n"
            f"计算依据归类判定原则列表（只能返回最匹配的序号，序号从1开始）：\n{numbered_rules}\n\n"
            "请以三级模块为单位规划 FPA 行：\n"
            "1. 默认生成 1 条三级模块级界面开发行，覆盖同一页面内的列表、查询条件、按钮、弹窗和状态组件。\n"
            "2. 非界面逻辑按功能动作拆分，一行一个动作。\n"
            "3. 不要为数据库表、字段、保存表动作单独生成行。\n"
            "4. 如果确实需要多条界面开发行，每条都必须给出 split_reason。\n\n"
            f"模块输入 JSON：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            "请直接输出 JSON，不要输出其他内容。格式：\n"
            '{"rows":[{"name":"<功能点名称>","type":"EI/ILF/EQ/EO/EIF","type_reason":"<类型理由>",'
            '"classification_basis_index":1,"explanation":"<计算依据说明>",'
            '"source_processes":["<功能过程名称>"],"split_reason":"<多界面拆分理由，可空>"}]}'
        )


@dataclass(frozen=True)
class StrictFpaProfile(CurrentProjectProfile):
    """严格 FPA 口径。"""

    name: str = "strict_fpa"
    version: str = "1"
    description: str = "严格 FPA 口径：按数据功能和事务功能拆分，不按界面/接口开发工作项拆分。"
    core_rules: str = STRICT_FPA_CORE_RULES

    def infer_type(self, name: str, desc: str = "") -> tuple[str, str]:
        text = f"{name} {desc}"
        if self._looks_like_external_data_function_name(name) and self._is_external_data_group(text):
            return "EIF", "明确引用外部系统维护的数据组，按 EIF。"
        name_action = self._explicit_transaction_type(name)
        if name_action:
            return name_action
        if self._is_external_data_group(text):
            return "EIF", "明确引用外部系统维护的数据组，按 EIF。"
        if self._looks_like_data_group(name, desc):
            return "ILF", "本系统维护的逻辑数据组，按 ILF。"
        desc_action = self._explicit_transaction_type(desc)
        if desc_action:
            return desc_action
        if any(k in text for k in EXTERNAL_SERVICE_CALL_HINTS):
            return "EI", "普通外部服务调用按触发事务处理，不能直接判 EIF。"
        return "EI", "未命中明确数据功能关键词，按事务功能 EI 兜底。"

    def _explicit_transaction_type(self, text: str) -> tuple[str, str] | None:
        if any(k in text for k in STRICT_EO_ACTIONS):
            return "EO", "事务功能产生派生或格式化输出，按 EO。"
        if any(k in text for k in STRICT_EQ_ACTIONS):
            return "EQ", "事务功能读取数据且无派生输出，按 EQ。"
        if any(k in text for k in STRICT_EI_ACTIONS):
            return "EI", "事务功能进入或改变系统边界内数据，按 EI。"
        return None

    def _looks_like_external_data_function_name(self, name: str) -> bool:
        return (
            any(noun in name for noun in EXTERNAL_DATA_GROUP_NOUNS)
            and not any(action in name for action in STRICT_EI_ACTIONS + STRICT_EQ_ACTIONS + STRICT_EO_ACTIONS)
        )

    def has_obvious_conflict(self, name: str, desc: str, ai_type: str) -> bool:
        text = f"{name} {desc}"
        if any(k in text for k in ["界面开发", "接口开发", "逻辑处理开发", "按钮", "弹窗"]):
            return True
        if any(k in text for k in EXTERNAL_SERVICE_CALL_HINTS):
            return ai_type == "EIF"
        name_action = self._explicit_transaction_type(name)
        return name_action is not None and name_action[0] != ai_type

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
        import json

        configured_prompt = _render_configured_fpa_prompt(self.name, self.core_rules, group, judgement_rules, domain_context)
        if configured_prompt:
            return configured_prompt
        numbered_rules = _numbered_judgement_rules(judgement_rules)
        payload = _prompt_payload(group, domain_context)
        return (
            f"{self.core_rules}\n\n"
            f"计算依据归类判定原则列表（只能返回最匹配的序号，序号从1开始）：\n{numbered_rules}\n\n"
            "请以严格 FPA 口径规划本三级模块的 FPA 行：\n"
            "1. 先识别数据功能：本系统维护的数据组为 ILF，外部维护且本系统引用的数据组为 EIF。\n"
            "2. 再识别事务功能：新增/修改/删除/保存/提交/审批/导入为 EI，查询/查看/详情为 EQ，导出/报表/下载文件为 EO。\n"
            "3. 禁止输出界面开发、接口开发、逻辑处理开发、按钮、弹窗、数据库表或字段行。\n"
            "4. 普通外部服务调用不要直接输出 EIF，除非明确引用外部维护的数据组。\n\n"
            f"模块输入 JSON：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            "请直接输出 JSON，不要输出其他内容。格式：\n"
            '{"rows":[{"name":"<功能点名称>","type":"EI/ILF/EQ/EO/EIF","type_reason":"<类型理由>",'
            '"classification_basis_index":1,"explanation":"<计算依据说明>",'
            '"source_processes":["<功能过程名称>"],"split_reason":""}]}'
        )

    def _is_external_data_group(self, text: str) -> bool:
        has_external_source = any(rule.matches(text) for rule in self._external_data_group_rules())
        has_maintenance_hint = any(k in text for k in EXTERNAL_MAINTAINED_HINTS)
        has_data_noun = any(k in text for k in EXTERNAL_DATA_GROUP_NOUNS)
        return has_data_noun and (has_external_source or has_maintenance_hint)

    def _looks_like_data_group(self, name: str, desc: str = "") -> bool:
        text = f"{name} {desc}"
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
        if self._is_external_data_group(all_text):
            data_functions.append((
                self._external_data_name(all_text, l3),
                "EIF",
                "外部系统维护、本系统引用的数据组，按 EIF。",
            ))
            return data_functions
        if any(k in all_text for k in ["维护", "保存", "新增", "添加", "修改", "编辑", "删除", "导入", "配置"]):
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

    def _external_data_group_rules(self) -> list[ExternalDataGroupRule]:
        rules = list(DEFAULT_EXTERNAL_DATA_GROUP_RULES)
        try:
            from ai_gen_reimbursement_docs.config_utils import load_fpa_external_data_rules
            configured_rules = load_fpa_external_data_rules()
        except Exception:
            configured_rules = []
        for item in configured_rules:
            aliases = tuple(str(alias).strip() for alias in item.get("source_aliases", []) if str(alias).strip())
            data_name = str(item.get("data_name") or "").strip()
            nouns = tuple(str(noun).strip() for noun in item.get("data_nouns", []) if str(noun).strip())
            if aliases and data_name:
                rules.append(ExternalDataGroupRule(aliases, data_name, nouns or tuple(EXTERNAL_DATA_GROUP_NOUNS)))
        return rules

    def _extract_external_data_name(self, text: str) -> str:
        patterns = [
            r"(?:引用|读取|使用|选择|同步)([^，。；、\s]{2,24}(?:数据组|主数据|基础数据|档案|信息|记录|账号|账户|单据))",
            r"([^，。；、\s]{2,24}(?:数据组|主数据|基础数据|档案|信息|记录|账号|账户|单据))(?:由|为)?(?:外部应用|外部系统|第三方系统|外部|第三方)[^，。；、\s]{0,12}(?:维护|提供)",
            r"(?:本系统不维护)([^，。；、\s]{2,24}(?:数据组|主数据|基础数据|档案|信息|记录|账号|账户|单据))",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return self._clean_external_data_name(match.group(1))
        return ""

    def _clean_external_data_name(self, name: str) -> str:
        for prefix in ["外部应用维护的", "外部系统维护的", "第三方系统维护的", "外部维护的", "本系统不维护的"]:
            if name.startswith(prefix):
                name = name[len(prefix):]
        return name.strip(" 的。；，、")

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
        return names

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


CURRENT_PROJECT_PROFILE = CurrentProjectProfile()
STRICT_FPA_PROFILE = StrictFpaProfile()
FPA_PROFILES = {
    CURRENT_PROJECT_PROFILE.name: CURRENT_PROJECT_PROFILE,
    STRICT_FPA_PROFILE.name: STRICT_FPA_PROFILE,
}


def get_fpa_profile(name: str = "current_project") -> CurrentProjectProfile:
    profile = FPA_PROFILES.get(name or CURRENT_PROJECT_PROFILE.name)
    if profile is not None:
        return profile
    raise ValueError(f"未知 FPA profile: {name}")
