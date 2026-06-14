# gen-fpa multi_uis 改名 multi_ui 实施清单

日期：2026-06-14

状态：待实施

## 背景

`gen-fpa` 当前内置多界面口径使用 `multi_uis` 作为 profile、kind、配置键前缀、规则集前缀、prompt 前缀、测试 fixture 名称和文档标识。

该命名不够自然，后续统一改为：

```text
multi_ui
```

本系统尚未上线，本次改名不保留旧版本兼容路径，不新增 `multi_uis` 别名，不做自动迁移。实施后，运行参数、配置示例、Web 选项、测试和现行文档统一使用 `multi_ui`。

## 目标行为

- CLI、Web、API 显式选择多界面口径时使用 `multi_ui`。
- `fpa_config.yaml` 中多界面 profile 名称、`kind`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt`、`calculation_explanation_rules` 等引用统一使用 `multi_ui` 前缀。
- 代码中的多界面行为分支以 `kind == "multi_ui"` 判断。
- 审阅、校验、prompt payload、agent review contract、golden fixture 报告中记录的 profile/kind/contract 统一使用 `multi_ui`。
- 用户文档和当前设计文档不再把 `multi_uis` 作为现行可选项。
- 历史验证记录如果需要保留旧运行名称，必须明确标注为历史记录，不得作为当前配置示例。

## 不在本次范围

- 不改 `gen-fpa` 命令名。
- 不调整多界面口径的业务语义。
- 不修改 FPA 结果表用户可见术语；相关页面仍遵循 `新增/修改功能点`、`类型`、`计算依据归类`、`计算依据说明`、`生成方式`。
- 不新增兼容层、迁移器或旧名提示分支。
- 不重构 `unified_ui`、`strict_fpa`、`ui_api_mapping` 的行为。

## 文件范围

### 代码与配置

- `ai_gen_reimbursement_docs/fpa_profiles.py`
  - 类名、默认 `name`、`kind` 返回值、contract 名称、kind 分支判断。
  - 与多界面审阅、拆分理由、质量检查相关的 profile/kind 字符串。
- `ai_gen_reimbursement_docs/config_utils.py`
  - `VALID_FPA_PROFILE_KINDS` 中的 `multi_uis` 改为 `multi_ui`。
  - profile 解析、配置校验、prompt 加载相关错误信息中的旧名。
- `ai_gen_reimbursement_docs/fpa_stability_sampler.py`
  - 默认 profile、rule_set、preset 中的 `multi_uis` 改为 `multi_ui`。
- `config/fpa_config.yaml.example`
  - `profiles.multi_uis` 改为 `profiles.multi_ui`。
  - `kind: multi_uis` 改为 `kind: multi_ui`。
  - `multi_uis_rs/_cr/_sp/_up/_ce/_json` 改为 `multi_ui_rs/_cr/_sp/_up/_ce/_json`。
  - prompt 文本中作为配置标识出现的 `multi_uis` 改为 `multi_ui`；业务语义“多界面口径”不变。
- `web_app/routes/tasks.py`
  - `/api/fpa/options` 或静态 label 映射中的旧名。
- `web_app/src/composables/useFpaOptions.ts`
  - 前端默认 profile 选项中的 `name`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt`。

### 测试

- `tests/test_config_utils.py`
- `tests/test_fpa_profiles.py`
- `tests/test_fpa_agent_review.py`
- `tests/test_fpa_stability_ci_script.py`
- `tests/fpa_profiles/test_multi_uis_harness.py`
- `tests/fpa_profiles/test_profile_prompt_payload_contract.py`
- `tests/fpa_profiles/test_profile_agent_review_contract.py`
- `tests/fixtures/fpa_profile_golden_cases/profile_agent_review_contract_cases.json`

实施时建议把 `tests/fpa_profiles/test_multi_uis_harness.py` 重命名为：

```text
tests/fpa_profiles/test_multi_ui_harness.py
```

如果 fixture case id 使用 `multi_uis_*`，同步改为 `multi_ui_*`。

### 文档

- `README.md`
- `docs/system-overview.html`
- `docs/fpa/fpa-profiles.md`
- `docs/fpa/fpa-stability-ci.md`
- `docs/fpa/gen-fpa-output-stability.md`
- `docs/fpa/gen-fpa-implementation-notes.md`
- `docs/fpa/calculation-basis-explanation-rules.md`
- `docs/fpa/validation-runs/multi-profile-run-template.md`
- `docs/web-ui/generation-page-compact-controls-todo.md`

历史验证记录可按两种方式处理：

1. 如果文档描述的是当前推荐命令或配置样例，改为 `multi_ui`。
2. 如果文档记录的是历史真实运行结果，可保留文件名和历史文本中的 `multi_uis`，但在开头补充“历史记录使用旧名，当前 profile 为 `multi_ui`”。

涉及历史记录的候选文件：

- `docs/fpa/validation-runs/2026-06-09-multi-uis-real-model-recommended.md`
- `docs/fpa/validation-runs/2026-06-09-multi-profile-real-model.md`
- `docs/fpa/validation-runs/2026-06-09-multi-profile-real-model-hardened.md`

## 实施步骤

### 1. 先改配置入口

修改 `config/fpa_config.yaml.example` 和 `config_utils.py`。

验收点：

- `multi_ui` 是有效 profile kind。
- `multi_uis` 不再是有效 profile kind。
- 示例配置完整包含 `multi_ui` profile。
- 旧名不作为默认值、候选项或兼容别名出现。

### 2. 再改 profile 行为实现

修改 `fpa_profiles.py` 中所有 profile 名、kind 名、contract 名和分支判断。

建议命名：

```text
MultiUiProfile
MULTI_UI_CORE_RULES
multi_ui_contract
```

验收点：

- `multi_ui` 仍保持原多界面口径：允许按独立页面、独立业务对象、独立业务流程或独立用户端拆分。
- 多界面开发行仍按 EI 识别。
- `split_reason` 或拆分理由仍进入 check/review 元数据。
- 非界面业务动作行仍复用 `unified_ui` 的类型规则。

### 3. 改 Web/API 选项

修改后端 label 映射和前端默认 options。

验收点：

- Web 配置页显示“多界面口径”，内部 profile name 为 `multi_ui`。
- 保存配置时写入 `active_output_template_profile` 联动字段后，不再产生 `multi_uis`。
- API 返回的 `profile`、`kind`、`rule_set`、prompt key 均为新名。

### 4. 改测试和 fixture

先批量替换测试中的断言和 fixture，再按失败信息处理遗漏分支。

建议优先跑：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_config_utils.py tests/test_fpa_profiles.py tests/fpa_profiles/test_profile_prompt_payload_contract.py tests/fpa_profiles/test_profile_agent_review_contract.py
```

再跑：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_fpa_agent_review.py tests/test_fpa_stability_ci_script.py tests/fpa_profiles/test_multi_ui_harness.py
```

### 5. 改文档

先改当前入口文档和配置说明，再处理历史记录。

优先级：

1. `README.md`
2. `docs/system-overview.html`
3. `docs/fpa/fpa-profiles.md`
4. `docs/fpa/gen-fpa-output-stability.md`
5. `docs/fpa/fpa-stability-ci.md`
6. `docs/fpa/validation-runs/multi-profile-run-template.md`

历史运行记录按“当前示例改名、历史事实保留并加注”的原则处理。

### 6. 全仓收尾检查

执行：

```powershell
rg -n "multi_uis|multi-uis|MultiUis|MULTI_UIS" .
```

允许残留的情况仅限：

- 历史验证记录中明确标注的旧运行名。
- 文件名本身作为历史记录保留。
- 本实施清单中描述旧名来源。

不允许残留：

- 代码分支判断。
- 配置示例。
- Web/API options。
- README 当前命令示例。
- 测试期望值。
- prompt payload contract 当前断言。

## 建议测试矩阵

基础配置与 profile：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_config_utils.py tests/test_fpa_profiles.py
```

profile contract 与 harness：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/fpa_profiles/test_profile_prompt_payload_contract.py tests/fpa_profiles/test_profile_agent_review_contract.py tests/fpa_profiles/test_multi_ui_harness.py
```

生成与审阅关键路径：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_gen_fpa_ai.py tests/test_gen_fpa_preview.py tests/test_fpa_agent_review.py
```

稳定性脚本：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_fpa_stability_sampler.py tests/test_fpa_stability_ci_script.py
```

改动完成后的文档和字符串检查：

```powershell
git diff --check
rg -n "multi_uis|multi-uis|MultiUis|MULTI_UIS" .
```

## 验收标准

- `--fpa-profile multi_ui` 可正常解析并执行。
- `--fpa-profile multi_uis` 不再作为有效 profile 通过。
- `config/fpa_config.yaml.example` 中不存在现行 `multi_uis` 配置键。
- `/api/fpa/options` 返回 `multi_ui`，显示名仍为“多界面口径”。
- Web 默认选项和保存链路使用 `multi_ui`。
- agent review / prompt payload / golden fixture contract 记录 `profile: multi_ui`、`profile_kind: multi_ui`、`contract: multi_ui_contract`。
- 多界面口径原有行为不变：多界面拆分、EI 类型、拆分理由元数据、非界面业务动作补充均保持。
- 当前用户文档和设计文档不再把 `multi_uis` 作为现行 profile 名。
- 全仓 `rg` 检查中，旧名只剩历史记录或本实施清单里的说明性文本。

## 风险与控制

- 风险：只改 profile 名但漏改 kind，导致配置能选中但行为回退。
  - 控制：contract 测试必须同时断言 `profile`、`profile_kind`、`contract`。
- 风险：Web options 仍返回旧名，导致前端保存旧配置。
  - 控制：补充或更新 `/api/fpa/options` 测试，断言返回 `multi_ui`。
- 风险：prompt 或 JSON contract 中仍写旧名，影响真实模型稳定性报告。
  - 控制：测试 prompt payload 中的 profile/kind/contract，并全仓搜索旧名。
- 风险：历史验证文档改名后失去追溯性。
  - 控制：历史运行记录允许保留旧名，但必须显式标注当前 profile 已改为 `multi_ui`。
- 风险：测试文件重命名后 CI 仍引用旧路径。
  - 控制：全仓搜索 `test_multi_uis_harness.py`，同步更新文档和脚本引用。

## 推荐提交拆分

如果一次提交完成，提交标题建议：

```text
Rename multi_uis FPA profile to multi_ui
```

如果拆成两次提交：

1. `Rename multi_uis profile in FPA code and tests`
2. `Update multi_ui FPA documentation`

本仓库要求每轮修改结束后创建提交；如果按本清单实施，提交前必须检查 `git status`，只纳入本次相关文件。
