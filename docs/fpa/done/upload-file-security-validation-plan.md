# 上传文件安全验证实施方案

## 背景

当前系统支持多种文件上传与导入：

- `POST /api/run-upload`
- `POST /api/fpa/preview-module`
- `POST /api/fpa/preview-modules`
- `POST /api/templates/spec/import`
- 自定义输出模板上传

现有实现只做了少量入口级约束，例如：

- 登录态/本机权限控制
- 文件名使用 `Path(file.filename).name`
- 部分场景下的扩展名检查
- 模板在后续解析阶段做结构预检

这不足以构成完整安全验证。为了降低伪装文件、路径穿越、ZIP 异常包、超大文件和恶意模板带来的风险，需要补一层统一上传安全网关。

## 目标

本方案的目标不是“让所有文件都能被接受”，而是“只有符合安全边界的文件才允许进入业务解析”。

目标行为：

1. 所有上传入口先经过统一安全校验。
2. 统一拒绝 `.xlsm`，只允许 `.xlsx`、`.docx` 等明确白名单。
3. 不允许仅靠浏览器 `accept` 或文件扩展名判断安全性。
4. 对 Office Open XML 文件进行魔数与包结构校验。
5. 对 ZIP 类文件做基础炸弹防护。
6. 落盘前后都保留明确、可审计的错误原因。

## 策略决策

### 1. 明确禁止 `.xlsm`

原因：

- `.xlsm` 可能携带宏，安全面明显大于普通 `.xlsx`。
- 当前系统不需要宏能力来完成生成、预览、导入。
- 关闭 `.xlsm` 能显著缩小攻击面，也让用户行为更容易理解。

结论：

- 上传入口一律拒绝 `.xlsm`
- 输出模板与导入模板统一只接受：
  - `.xlsx`
  - `.docx`
- 若未来确需宏模板，应单独设计受限白名单，不沿用本方案默认放开策略

### 2. 文件大小限制

建议默认阈值：

- 普通功能清单 `.xlsx`：`30MB`
- 输出模板 `.xlsx` / `.docx`：`50MB`
- 任何上传项的请求体：以服务端配置统一控制

超过阈值直接返回 `400`，禁止继续解析。

### 3. 内容真实性校验

必须校验：

- 文件扩展名
- 文件内容魔数
- ZIP 包基础结构
- Office 文件关键 entry 是否存在

不得只依赖：

- 浏览器 `accept`
- 前端传入的原始文件名
- `Content-Type` 请求头

## 统一校验层设计

建议新增一个统一模块，例如：

- `web_app/services/upload_security.py`

建议职责：

1. 识别上传用途
   - `input_xlsx`
   - `spec_docx`
   - `output_template_xlsx`
2. 校验扩展名
3. 校验大小
4. 校验魔数
5. 校验 ZIP 结构
6. 校验 Office Open XML 关键文件
7. 返回规范化的安全错误

建议接口形态：

```python
validate_upload_file(
    upload_file,
    *,
    purpose: str,
    max_size_bytes: int,
) -> ValidatedUpload
```

其中 `ValidatedUpload` 应至少包含：

- 原始文件名
- 安全后文件名
- 内容字节
- 扩展名
- 体积
- 校验通过标记

## 校验规则

### A. 通用规则

1. 文件不能为空
2. 文件名不能为空
3. 文件名只作为展示，不直接用于路径拼接
4. 文件扩展名必须在白名单中
5. 文件大小必须在限制内

### B. `.xlsx` 校验

1. 仅允许 `.xlsx`
2. 文件必须是 ZIP 结构
3. 必须包含 `[Content_Types].xml`
4. 必须包含 `xl/workbook.xml`
5. 不允许 ZIP 中存在：
   - 绝对路径
   - `../`
   - Windows 盘符路径
   - 空文件名
6. 检查 entry 数量与解压后总量，防止 ZIP bomb

### C. `.docx` 校验

1. 仅允许 `.docx`
2. 文件必须是 ZIP 结构
3. 必须包含 `[Content_Types].xml`
4. 必须包含 `word/document.xml`
5. 同样做 ZIP 路径与体积检查

### D. `.xlsm` 处理

1. 一律拒绝
2. 错误提示直接说明“不支持 `.xlsm`”
3. 不进入后续解析或预检流程

## 入口改造范围

建议统一接入以下位置：

1. `web_app/routes/tasks.py`
   - `/api/run-upload`
   - `/api/fpa/preview-module`
   - `/api/fpa/preview-modules`

2. `web_app/routes/templates.py`
   - `/api/templates/spec/import`

3. `web_app/services/template_service.py`
   - 自定义模板保存
   - spec 模板导入

## 业务预检与安全校验的边界

要明确分层：

### 第一层：安全校验

负责回答“这个文件能不能碰”。

输出：

- 通过 / 拒绝
- 拒绝原因

### 第二层：业务预检

负责回答“这个文件适不适合当前业务”。

例如：

- 模板 manifest 是否匹配
- sheet / 占位符 / 命名单元格是否齐全
- Word 模板是否含必要锚点

业务预检不能替代安全校验。

## 错误处理规范

建议统一返回 400，并使用短句中文提示：

- `未选择文件`
- `仅支持上传 .xlsx 文件`
- `不支持上传 .xlsm 文件`
- `文件过大，超过 30MB 限制`
- `文件不是有效的 Office 文档`
- `ZIP 结构异常，疑似伪装文件`

要求：

- 不暴露服务端绝对路径
- 不回显内部异常堆栈
- 不把 Python / openpyxl / python-docx 的原始错误直接吐给前端

## 实施步骤

### 第 1 步：新增统一上传安全模块

实现：

- 扩展名白名单
- 大小限制
- Office/ZIP 结构验证
- 统一错误类型

### 第 2 步：接入运行上传入口

先改：

- `/api/run-upload`
- `/api/fpa/preview-module`
- `/api/fpa/preview-modules`

因为这是最核心的用户上传通路。

### 第 3 步：接入模板导入入口

再改：

- `/api/templates/spec/import`
- 自定义输出模板保存逻辑

### 第 4 步：补测试

至少覆盖：

- 正常 `.xlsx` 上传
- 正常 `.docx` 上传
- `.xlsm` 被拒绝
- 伪装扩展名文件被拒绝
- 空文件被拒绝
- 超大文件被拒绝
- ZIP 路径穿越被拒绝
- 缺少关键 Office entry 被拒绝

## 建议测试文件

- `tests/test_upload_security.py`
- `tests/test_web_tasks.py`
- `tests/test_template_service.py`
- `tests/test_template_manifest.py`

## 验收标准

1. 所有上传入口都走统一安全校验。
2. `.xlsm` 上传明确失败。
3. `.txt` 改名成 `.xlsx` 不能绕过校验。
4. ZIP bomb 类样本不能进入业务解析。
5. 业务预检保留原有能力，但只作用于已通过安全校验的文件。
6. 单测覆盖主要拒绝路径和正常路径。

## 风险与取舍

1. 严格 ZIP 校验可能误伤少数非常复杂的模板，但这是可接受的安全取舍。
2. `.xlsm` 关闭后，历史上依赖宏模板的用户需要迁移到 `.xlsx`。
3. 如果未来要支持更大的模板，需要同步调整大小阈值与 ZIP 检查阈值，而不是单独放松某一个入口。

## 结论

本方案可以直接落地实施。最关键的策略已经固定：

- 统一上传安全校验
- 明确禁止 `.xlsm`
- 业务预检与安全校验分层
- 全部上传入口共用一套规则

## 归档说明

已实施并归档。实现落点包括：

- `web_app/services/upload_security.py`：统一上传安全校验、OOXML ZIP 结构检查、`.xlsm` 拒绝、大小限制。
- `web_app/routes/tasks.py`：`/api/run-upload`、`/api/fpa/preview-module`、`/api/fpa/preview-modules` 接入上传校验。
- `web_app/services/template_service.py`：自定义输出模板保存与 Word 模板导入接入上传校验。
- `web_app/src/components/TemplateUpload.vue`：自定义 Excel 输出模板选择提示移除 `.xlsm`。
- `tests/test_upload_security.py`、`tests/test_web_tasks.py`、`tests/test_web_template_routes.py`：覆盖正常 OOXML、`.xlsm`、伪装文件、空文件、超大文件、ZIP 路径异常和缺少关键 entry 等路径。
