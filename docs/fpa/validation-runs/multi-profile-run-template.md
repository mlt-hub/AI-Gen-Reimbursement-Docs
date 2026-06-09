# FPA 多 Profile 真实模型抽样记录模板

日期：

## 运行指纹

```text
输入样例：
执行人：
执行时间：
run_id：
模型端点：
模型：
fixture suite：
```

## Profile 记录

### strict_fpa

```text
profile: strict_fpa
kind:
strategy:
rule_set:
system_prompt:
user_prompt:
row count:
warning count:
check.xlsx:
```

观察结论：

- profile 语义是否符合预期：
- 类型规则是否稳定：
- 命名是否使用完整模块路径：
- 来源追溯是否完整：
- 是否需要调整 prompt：

### unified_ui

```text
profile: unified_ui
kind:
strategy:
rule_set:
system_prompt:
user_prompt:
row count:
warning count:
check.xlsx:
```

观察结论：

- 是否保持同一三级模块统一界面口径：
- 是否避免按按钮、查询条件、字段过度拆分：
- 非界面业务动作行是否稳定：
- 来源追溯是否完整：
- 是否需要调整 prompt：

### multi_uis

```text
profile: multi_uis
kind:
strategy:
rule_set:
system_prompt:
user_prompt:
row count:
warning count:
check.xlsx:
```

观察结论：

- 多界面拆分是否有明确理由：
- 拆分理由是否进入 check/review 元数据：
- 同名多界面行是否提示人工审阅：
- 非界面业务动作行是否稳定：
- 是否需要调整 prompt：

### ui_api_mapping

```text
profile: ui_api_mapping
kind:
strategy:
rule_set:
system_prompt:
user_prompt:
row count:
warning count:
check.xlsx:
```

观察结论：

- 功能过程默认界面开发行是否固定为 EI：
- 功能过程默认接口开发行是否固定为 ILF：
- 明确接口/后端调用行是否固定为 ILF：
- 明确接口/后端调用行是否只来自显式输入：
- 默认接口行与明确接口行是否同时保留：
- 是否需要调整 prompt：

## 问题清单

| profile | 问题 | 影响 | 建议处理 | 是否阻塞 |
|---|---|---|---|---|
|  |  |  |  |  |

## 总结

```text
通过 profile：
需复测 profile：
阻塞项：
后续动作：
```
