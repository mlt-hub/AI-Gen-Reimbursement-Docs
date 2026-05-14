"""全局常量定义 —— 消除散落在各处的硬编码值。

所有硬编码的模型名、路径、Sheet 名称、列索引等集中在此管理。
后续可改为从配置文件读取，无需修改业务代码。
"""

# ---- Excel 功能点拆分表 列索引（输出模板结构） ----
COL_FP_SUB_PROCESS = 8   # 子过程描述（警告标记列）
COL_FP_MOVE_TYPE = 9     # 数据移动类型
COL_FP_CFP = 13          # CFP 公式列
FP_DATA_START_ROW = 6    # 数据起始行
FP_TOTAL_COLS = 14       # 总列数

# 列号 → 字段名映射（excel_writer 写入时使用）
FP_COL_KEY_MAP = {
    1: "project", 2: "module_l1", 3: "module_l2", 4: "module_l3",
    5: "user", 6: "trigger", 7: "process", 8: "sub_process",
    9: "move_type", 10: "data_group", 11: "data_attrs",
    12: "reuse", 13: "cfp",
}

# 需要左对齐的列
FP_LEFT_ALIGN_COLS = (8, 10, 11)

# ---- FPA 工作量评估 列索引 ----
FPA_COL_SEQ = 1           # 序号
FPA_COL_SUBSYSTEM = 2     # 子系统(模块)
FPA_COL_ASSET = 3         # 资产标识
FPA_COL_FUNC_POINT = 4    # 新增/修改功能点
FPA_COL_TYPE = 5          # 类型
FPA_COL_CLASSIFICATION = 6  # 计算依据归类
FPA_COL_EXPLANATION = 7   # 计算依据说明（需左对齐换行）
FPA_COL_STATUS = 8        # 变更状态
FPA_COL_FORMULA_BASE = 9  # 基准值（公式列）
FPA_COL_ADJUST = 10       # 调整值
FPA_COL_ELEMENTS = 11     # 要素数量
FPA_COL_FORMULA_WORKLOAD = 12  # FPA工作量（公式列）
FPA_TOTAL_COLS = 14       # 总列数

# 列号 → 字段名映射
FPA_COL_KEY_MAP = {
    1: "序号", 2: "子系统(模块)", 3: "资产标识", 4: "新增/修改功能点",
    5: "类型", 6: "计算依据归类", 7: "计算依据说明", 8: "变更状态",
    10: "调整值", 11: "要素数量",
}

# ---- 项目需求清单 列索引 ----
REQ_COL_SEQ = 1           # 序号
REQ_COL_PROJECT = 2       # 项目名称
REQ_COL_SUBSYSTEM = 3     # 子系统
REQ_COL_L1 = 4            # 一级模块
REQ_COL_L2 = 5            # 二级模块
REQ_COL_L3 = 6            # 三级模块
REQ_COL_PROC_TYPE = 7     # 功能过程类型
REQ_COL_WORKLOAD = 8      # 送审工作量
REQ_COL_CFP = 9           # 送审功能点
REQ_TOTAL_COLS = 9        # 总列数

# 列号 → 字段名映射
REQ_COL_KEY_MAP = {
    1: "序号", 2: "项目名称", 3: "子系统", 4: "一级模块",
    5: "二级模块", 6: "三级模块", 7: "功能过程类型",
}

