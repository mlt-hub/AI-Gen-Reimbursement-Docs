"""全局常量定义 —— 消除散落在各处的硬编码值。

所有硬编码的模型名、路径、Sheet 名称、列索引等集中在此管理。
后续可改为从配置文件读取，无需修改业务代码。
"""

# ---- AI 默认值 ----
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_MAX_TOKENS = 6000

# ---- COSMIC 业务默认值 ----
DEFAULT_INITIATOR = "操作员"
DEFAULT_RECEIVER = "地市后台"

# ---- 章节检测默认值 ----
DEFAULT_CHAPTER_NUMBER = "4"
DEFAULT_CHAPTER_KEYWORD = "功能需求"
DEFAULT_END_CHAPTER_NUMBER = "5"

# ---- 模板目录 ----
TEMPLATE_DIR = "data/templates"

# ---- 模板文件路径 ----
TEMPLATE_FUNC_POINT = f"{TEMPLATE_DIR}/项目功能点拆分表-模板.xlsx"
TEMPLATE_FPA = f"{TEMPLATE_DIR}/FPA工作量评估-模板.xlsx"
TEMPLATE_REQUIRE = f"{TEMPLATE_DIR}/项目需求清单-模板.xlsx"
TEMPLATE_SPEC = f"{TEMPLATE_DIR}/项目需求说明书-模板.docx"

# ---- 模板映射（用于 excel_source 中 resolve） ----
TEMPLATE_MAP = {
    "FPA工作量评估-模板": TEMPLATE_FPA,
    "项目需求说明书-模板": TEMPLATE_SPEC,
    "项目功能点拆分表-模板": TEMPLATE_FUNC_POINT,
    "项目需求清单-模板": TEMPLATE_REQUIRE,
}

# ---- Excel Sheet 名称 ----
SHEET_META = "1、工单需求-元数据录入"
SHEET_FUNC_CONTENT = "2、功能清单-内容录入"
SHEET_FPA_META = "3、FPA工作量评估-元数据录入"
SHEET_SPEC_META = "4、项目需求说明书-元数据录入"
SHEET_WORKLOAD_META = "5、预估工作量-元数据录入"
SHEET_COSMIC_META = "6、项目功能点拆分表-元数据录入"
SHEET_REQUIRE_META = "7、项目需求清单-元数据录入"
SHEET_TEMPLATE_CONFIG = "8、各文档-模板路径录入"

# 元数据 Sheet 列表（按解析顺序）
META_SHEETS = [
    (SHEET_META, "project_info"),
    (SHEET_FPA_META, "fpa_meta"),
    (SHEET_SPEC_META, "docx_meta"),
    (SHEET_WORKLOAD_META, "workload_meta"),
    (SHEET_COSMIC_META, "cosmic_meta"),
    (SHEET_REQUIRE_META, "require_meta"),
]

# ---- Excel 功能点拆分表 列索引 ----
COL_FP_PROJECT = 1
COL_FP_MODULE_L1 = 2
COL_FP_MODULE_L2 = 3
COL_FP_MODULE_L3 = 4
COL_FP_USER = 5
COL_FP_TRIGGER = 6
COL_FP_PROCESS = 7
COL_FP_SUB_PROCESS = 8
COL_FP_MOVE_TYPE = 9
COL_FP_DATA_GROUP = 10
COL_FP_DATA_ATTRS = 11
COL_FP_REUSE = 12
COL_FP_CFP = 13
FP_DATA_START_ROW = 6
FP_TOTAL_COLS = 14

# 列号 → 字段名映射（excel_writer 写入时使用）
FP_COL_KEY_MAP = {
    1: "project", 2: "module_l1", 3: "module_l2", 4: "module_l3",
    5: "user", 6: "trigger", 7: "process", 8: "sub_process",
    9: "move_type", 10: "data_group", 11: "data_attrs",
    12: "reuse", 13: "cfp",
}

# 需要左对齐的列
FP_LEFT_ALIGN_COLS = (8, 10, 11)

# ---- FPA 接收方类型 ----
RECEIVER_TYPE_MAP = {
    "后台": "后台管理员",
    "管理": "后台管理员",
    "普通": "普通用户",
    "渠道": "渠道人员",
}
