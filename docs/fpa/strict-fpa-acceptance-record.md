# strict_fpa 人工验收记录

归档日期：2026-06-02

本文档记录 `strict_fpa` profile 的人工验收结论。它补充自动化测试，不替代 `tests/fixtures/fpa_golden_cases/` 中的固定期望。

## 验收范围

```text
profile: strict_fpa
默认策略: ai_first
默认 rule_set: strict_fpa_rs
关注点:
- 不按界面开发 / 接口开发旧口径拆分。
- 本系统维护数据组按 ILF。
- 外部系统维护、本系统引用的数据组按 EIF。
- 普通外部服务调用不生成 EIF。
- EI / EQ / EO / ILF / EIF 类型判断可追溯。
- warning、AI 原始返回、规则命中详情和覆盖审核可进入 check.xlsx。
- AI cache 命中和领域上下文变更后的缓存失效可追溯。
```

## 固定样例人工复核

复核对象：

```text
tests/fixtures/fpa_golden_cases/*.json
tests/test_fpa_golden_fixture_reports.py
tests/test_gen_fpa_strict_profile.py
tests/test_fpa_external_data_rules.py
```

结论：

```text
通过。
strict_fpa 固定样例已覆盖 OA 审批、主数据平台组织引用、支付网关退款、短信通知、CRM / ERP 外部数据引用、内部组织维护、多个 ILF / EIF 并存、外部引用与本系统关系数据并存等场景。
自动化期望中不再出现“界面开发”“逻辑处理开发”旧拆分口径。
支付网关、短信平台等普通外部服务未被误判为 EIF。
```

## 逻辑事务合并口径复核

执行日期：2026-06-06

提交：

```text
7ae01cc6e842858a3ed91b00432b946fc33299b8
feat: merge strict fpa logical transactions
```

口径变更：

```text
strict_fpa 从逐功能过程事务计数，切换为逻辑事务合并口径。
输入中的功能过程类型只作为参考；当功能过程类型与名称或描述冲突时，以名称和描述为准。
processes 是候选业务步骤，不是功能点计数单位。
同一 ILF、同一业务对象、同一管理场景下的新增、修改、删除、启停、保存等维护动作合并为一个维护类 EI。
同一数据组、同一列表或查询界面的默认列表、条件搜索、按名称查询、筛选查询合并为一个查询类 EQ。
手机号校验、账号校验、权限校验、认证校验、短信发送、支付调用、OCR 调用、消息推送等普通外部服务调用不生成 EIF。
```

代表样例：

```text
垂直行业列表数据查询 + 查询垂直行业数据
= 垂直行业查询：EQ

添加垂直行业 + 编辑垂直行业 + 删除垂直行业
= 垂直行业维护：EI

新增垂直行业管理员 + 删除垂直行业管理员
= 垂直行业管理员维护：EI
```

更新范围：

```text
config/fpa_config.yaml.example
ai_gen_reimbursement_docs/fpa_profiles.py
ai_gen_reimbursement_docs/gen_fpa.py
tests/fixtures/fpa_golden_cases/vertical_industry_management.json
tests/test_gen_fpa_strict_profile.py
tests/test_fpa_profiles.py
tests/test_fpa_acceptance.py
tests/test_config_utils.py
docs/fpa/gen-fpa-output-stability.md
```

自动化验证：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

结果：

```text
449 passed, 2 skipped
```

验收结论：

```text
通过。
strict_fpa prompt、规则兜底、golden fixture、acceptance 汇总和测试断言已对齐到逻辑事务合并口径。
垂直行业管理样例已覆盖维护类 EI 合并、查询类 EQ 合并、source_processes 合并来源记录。
AI 数据功能人工复核 warning 独立保留，不再因为同时存在类型冲突 warning 而丢失。
```

## 真实模型验收

执行日期：2026-05-31

前提：

```text
用户明确允许将 FPA 验收样例发送到已配置 LLM API。
模型端点: api.deepseek.com
模型: deepseek-v4-flash[1m]
脚本: scripts/run_fpa_real_model_validation.py
```

代表样例：

```text
mixed_internal_external_data_functions
payment_gateway_refund
master_data_org_reference
```

验收结论：

```text
通过。
三例均完成真实模型正式生成，FPA 行来源为 ai。
三例均生成 check.xlsx 五张 Sheet：FPA结果、覆盖审核、Warnings、规则命中详情、AI原始返回。
复跑同一输出目录后，AI原始返回 Sheet 来源为 ai_cache，缓存链路可用。
warning 来源可追溯到 postprocess.ai_first_type_conflict / coverage.missing_process。
规则命中详情记录 postprocess.ai_type_validation / postprocess.ai_first_type_conflict。
payment_gateway_refund 未将支付网关误拆成 EIF。
mixed_internal_external_data_functions 能同时保留本系统 ILF、外部 EIF、EI、EQ。
master_data_org_reference 能拆出选择事务 EI 和组织主数据 EIF。
```

观察：

```text
真实模型输出命名与 golden 规则结果不要求完全一致；例如 OA流程单据 / OA审批流程单据等自然命名差异属于可接受差异。
验收重点是拆分粒度、类型判断、说明质量、warning 可追溯、缓存与审核副本链路。
```

## 真实业务输入复核

执行日期：2026-05-31

输入：

```text
1111/md/0.1.gen-basedata-功能清单-模块树.md
1111/md/0.2.gen-basedata-录入文档元数据-模板.md
```

输入规模：

```text
功能过程: 56
三级模块: 19
```

rules_only 结果：

```text
FPA 行数: 65
类型分布: EI 31、EO 6、EQ 19、ILF 9
覆盖缺口: 0
warning: 0
汇总值: 96.0 人/天
AI原始返回 Sheet 来源: rules
```

ai_first 真实模型结果：

```text
FPA 行数: 69
类型分布: EI 29、EO 6、EQ 21、ILF 13
覆盖缺口: 0
warning: 40，均来自 postprocess.ai_first_type_conflict
汇总值: 98.0 人/天
AI原始返回 Sheet 来源: ai
```

验收结论：

```text
通过。
规则路径和真实模型路径均覆盖全部原始功能过程。
真实模型倾向于额外拆出数据组，ILF 数量高于规则路径，汇总值从 96.0 上升到 98.0。
查询 / 导出类功能能区分 EQ / EO。
AI 优先策略保留有效 AI type；与规则建议不一致时进入 postprocess.ai_first_type_conflict，便于人工审核。
```

## 覆盖链路复核

已通过自动化验证：

```text
预览与正式规则路径行结果一致。
mock AI warning 可进入预览 warnings、audit.warnings、正式 audit trace、check.xlsx 覆盖审核 / Warnings / AI原始返回 Sheet。
AI cache 命中后 audit trace 与 check.xlsx 的 AI原始返回 Sheet 标记为 ai_cache。
不同 profile / strategy 的 MD 汇总值与 Excel J×K/SUM 公式投影一致。
domain_context.json 会与元数据上下文合并进入 prompt，并纳入 AI cache key。
```

## 最终结论

```text
strict_fpa 当前可作为正式 FPA 审核前的生成口径使用。
生成结果仍建议结合 check.xlsx 进行人工复核，重点查看 postprocess.ai_first_type_conflict、coverage.missing_process、AI原始返回和规则命中详情。
当前无剩余必须阻塞发布的 strict_fpa 验收项。
```
