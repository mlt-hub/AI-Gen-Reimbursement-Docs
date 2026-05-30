# FPA 方案选择说明

日期：2026-05-30

## 可选方案

系统当前提供两套 FPA 生成口径：

```text
current_project：当前报账模板口径
strict_fpa：严格 FPA 口径
```

两套方案只影响 FPA 行规划、类型判断、AI prompt 和兜底规则，不改变 Excel 模板列结构。

## 如何选择

### 推荐使用 current_project 的场景

```text
目标是生成当前报账模板更容易接受的 FPA 工作量评估。
希望保留“界面开发 / 逻辑处理开发 / 查询处理开发 / 导出处理开发”等表达。
希望减少按钮、弹窗、查询条件、状态组件被拆得过细。
评审关注的是当前交付物格式和可解释性，而不是严格 FPA 方法学。
```

`current_project` 是默认方案。

### 推荐使用 strict_fpa 的场景

```text
目标是尽量贴近标准 FPA 方法。
希望按数据功能和事务功能拆分。
希望避免“界面开发”“接口开发”“逻辑处理开发”等开发工作项表达。
需要区分 ILF / EIF / EI / EQ / EO 的方法学含义。
```

`strict_fpa` 更适合方法学校准、内部复核、与标准 FPA 口径对齐。

## 输出差异

### 输入示例

```text
三级模块：垂直行业管理
三级模块描述：维护垂直行业基础信息、状态和管理员。

功能过程：
1. 查询垂直行业：按行业名称查询垂直行业列表。
2. 添加垂直行业：输入垂直行业名称并保存。
3. 编辑垂直行业：修改垂直行业名称并保存。
4. 删除垂直行业：删除指定垂直行业。
```

### current_project 输出形态

```text
【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-界面开发：EI
查询垂直行业-查询处理开发：EQ
添加垂直行业-逻辑处理开发：ILF
编辑垂直行业-逻辑处理开发：ILF
删除垂直行业-逻辑处理开发：ILF
```

特点：

```text
同一三级模块默认合并 1 条界面开发行。
查询、导出、导入会用更模板友好的命名。
新增、编辑、删除等内部维护动作通常按 ILF 兜底。
```

### strict_fpa 输出形态

```text
垂直行业信息：ILF
垂直行业管理员关系：ILF
查询垂直行业：EQ
添加垂直行业：EI
编辑垂直行业：EI
删除垂直行业：EI
```

特点：

```text
不生成界面开发行。
先识别本系统维护的数据组为 ILF，可包含主数据和关系数据。
再按事务功能识别 EI / EQ / EO。
新增、编辑、删除等改变系统数据的动作按 EI。
```

## 使用方式

### Web UI

在高级选项中选择：

```text
FPA 方案 -> 当前报账模板口径 / 严格 FPA 口径
```

FPA 预览区域也提供相同选择，预览结果标题会显示当前口径。

### CLI

```powershell
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile current_project
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile strict_fpa
```

全流程同样支持：

```powershell
ard --from-excel 功能清单.xlsx --gen-all --fpa-profile strict_fpa
```

### 配置文件

`~/.ai-gen-reimbursement-docs/system_config.yaml`：

```yaml
fpa_profile: current_project
```

可改为：

```yaml
fpa_profile: strict_fpa
```

CLI 参数优先于配置文件。

## 预览建议

建议在正式生成前先使用 FPA 预览检查 1 到 3 个典型三级模块：

```text
包含新增/编辑/删除的数据维护模块。
包含导入、导出、查询的模块。
包含外部用户中心、外部主数据或普通外部服务调用的模块。
```

重点看：

```text
是否选对了 profile。
是否出现不该出现的“界面开发 / 接口开发 / 逻辑处理开发”。
普通外部服务调用是否被误判为 EIF。
本系统维护的数据组是否识别为 ILF。
外部维护且本系统引用的数据组是否识别为 EIF。
```

## 当前边界

`strict_fpa` 目前是基础版严格口径：

```text
能覆盖常见 ILF / EIF / EI / EQ / EO 场景。
可从功能过程语义中识别主数据 + 管理员关系这类多个内部数据组。
外部数据组识别已形成代码内规则表，当前覆盖统一用户中心、CRM、客户中心、财务核算系统、ERP、OA、主数据平台等常见外部来源。
`system_config.yaml` 可通过 `fpa_external_data_rules` 扩展外部数据组规则；扩展规则只追加，不覆盖内置规则。
外部数据组规则表已有专门测试，正例覆盖已知外部来源，反例覆盖短信平台、支付网关、文件存储、地图服务、OCR 服务等普通外部服务。
AI 后处理会纠正明显类型冲突：普通外部服务调用误报为 EIF 时回退为 EI；名称本身明确表示外部数据组时仍保留 EIF。
如果 AI 返回“界面开发 / 接口开发 / 逻辑处理开发”等开发项名称，后处理会尽量规范为严格 FPA 的事务/数据功能名称。
更复杂的数据组识别仍依赖模块名称、模块描述和功能过程描述中的语义。
普通外部服务调用不会自动判 EIF。
Excel 模板列结构暂不随 profile 改动。
pipeline 工作量汇总建议由代码中的业务计算规则统一产生。
Excel 继续保留模板原有公式；Excel/LibreOffice 复算只作为可选校验。
```

如果严格 FPA 结果用于正式方法学审计，建议结合人工复核。

## 后续路线

后续增强事项当前暂缓推进。详尽任务池和可复制的恢复指令见：

```text
docs/dev/gen-fpa-implementation-notes.md
```

对应章节：

```text
暂缓推进任务池
后续恢复指令
```

优先做 Golden Case 升级的原因：

```text
能保护 current_project 和 strict_fpa 两套口径不退化。
能把“看起来合理”的规则变成可重复验收的样例。
后续恢复推进时，每增加一个真实项目口径，都可以先固化成样例，再改规则。
```

不建议过早配置化：

```text
当前规则仍在探索期。
如果没有足够真实样例，过早配置化会把不稳定口径固化成复杂配置。
更稳妥的路径是先积累 Golden Case，再把稳定规则补充到内置规则或 `fpa_external_data_rules`。
补充规则前后，应保持规则表单元测试、strict_fpa 行为测试、Golden Case 差异报告三层测试同时通过。
普通外部服务调用不要配置为外部数据组，否则会把服务调用误判为 EIF。
```

当前已落地固定 fixture 集：

```text
tests/fixtures/fpa_golden_cases/vertical_industry_management.json
tests/fixtures/fpa_golden_cases/customer_list_import.json
tests/fixtures/fpa_golden_cases/external_user_center_reference.json
tests/fixtures/fpa_golden_cases/crm_customer_archive_reference.json
tests/fixtures/fpa_golden_cases/erp_order_reference.json
tests/fixtures/fpa_golden_cases/sms_notification_service.json
```

自动差异报告测试：

```text
tests/test_fpa_golden_fixture_reports.py
```
