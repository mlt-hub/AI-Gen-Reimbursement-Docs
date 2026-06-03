# FPA 配置结构调整讨论记录

## 当前问题

当前 `fpa_config.yaml` 使用 `prompt_sets.<name>.system` 和 `prompt_sets.<name>.user` 保存同一组提示词中的 system/user 两段内容。

这个结构容易让人误解为 `custom_rules` 自身包含两类规则，而不是一次 LLM 调用中的两类消息。

## 已确认方向

1. 将 `prompt_sets` 拆分为两个顶层配置：
   - `system_prompt_sets`
   - `user_prompt_sets`
2. prompt set 与 FPA profile 的关联继续由 `profiles` 指定：
   - `profiles.<profile>.system_prompt` 指向 `system_prompt_sets.<name>`
   - `profiles.<profile>.user_prompt` 指向 `user_prompt_sets.<name>`
3. 在讨论完全敲定前，先维护本讨论记录；暂不直接修改正式文档、配置示例、代码和测试。

## 目标配置结构草案

```yaml
profile: custom_rules

profiles:
  custom_rules:
    strategy: rules_first
    rule_set: custom_rules_default
    system_prompt: custom_rules
    user_prompt: custom_rules

  strict_fpa:
    strategy: ai_first
    rule_set: strict_fpa_default
    system_prompt: strict_fpa
    user_prompt: strict_fpa

system_prompt_sets:
  custom_rules: |-
    ...

  strict_fpa: |-
    ...

user_prompt_sets:
  custom_rules: |-
    ${core_rules}
    ${judgement_rules}
    ${payload_json}

  strict_fpa: |-
    ${core_rules}
    ${judgement_rules}
    ${payload_json}

rule_sets:
  custom_rules_default: {}
  strict_fpa_default: {}
```

## 待确认问题

1. 是否保留字段名 `system_prompt` / `user_prompt`，还是改为更明确的 `system_prompt_set` / `user_prompt_set`。
2. 错误提示和来源标签是否使用：
   - `system_prompt_sets.custom_rules`
   - `user_prompt_sets.custom_rules`
3. 是否需要迁移脚本，或因系统尚未上线而直接替换旧结构。
4. 是否允许 system prompt 和 user prompt 使用不同名称，例如 `system_prompt: default_fpa`、`user_prompt: custom_rules_v2`。

## 迁移影响范围

预计需要同步调整：

1. `config/fpa_config.yaml.example`
2. `ai_gen_reimbursement_docs/config_utils.py`
3. FPA 配置、Prompt 加载、Web 任务相关测试
4. `docs/fpa/fpa-prompt-configuration.md`
5. `docs/fpa/fpa-profiles.md`
6. `docs/fpa/gen-fpa-implementation-notes.md`
7. README 中引用 FPA Prompt 配置结构的内容

## 后续实施计划

讨论敲定后再一次性更新正式文档、配置示例、代码和测试，并运行相关 Python 测试验证。
