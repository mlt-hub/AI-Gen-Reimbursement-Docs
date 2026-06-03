# FPA 计算依据归类判定原则配置化待办

## 背景

当前 `gen-fpa` 的「计算依据归类判定原则列表」由 FPA 输出模板 Excel 附录读取：

- 默认 sheet：`附录1-FPA评估方法说明`
- 读取范围：从第 2 行开始读取第 3 列非空文本
- 使用方式：生成 AI prompt 时按 `1) ...` 编号传入，AI 返回 `classification_basis_index`，后处理再映射为「计算依据归类」

该方式依赖输出模板内容。为了让判定原则可独立维护、可版本化、可在不同模板间复用，需要新增独立配置文件，并通过配置参数决定规则来源。

## 目标行为

新增独立配置文件存放「计算依据归类判定原则列表」。

默认从配置文件读取判定原则；只有显式配置为 `template` 时，才从 FPA 输出模板 Excel 附录读取。

当选择配置文件来源但配置文件缺失、格式错误或列表为空时，应抛出清晰错误，避免静默生成空的「计算依据归类」。

## 配置设计

### 新增配置参数

在 `fpa_config.yaml` 中新增：

```yaml
judgement_rules_source: config
```

可选值：

- `config`：从独立配置文件读取，作为默认值。
- `template`：从 FPA 输出模板 Excel 附录读取，保持当前模板读取行为。

非法值应报配置错误，例如：

```text
未知 FPA judgement_rules_source: xxx
```

### 新增独立配置文件

新增示例文件：

```text
config/fpa_judgement_rules.yaml.example
```

用户实际配置文件：

```text
配置目录/fpa_judgement_rules.yaml
```

建议格式：

```yaml
judgement_rules:
  - 按后台数据库变更的表个数计量
  - 按界面输入、查询、输出等事务功能计量
```

第一版只支持字符串列表，不引入 rule id、适用类型、说明等复杂结构。

## 执行逻辑

`gen-fpa` 读取判定原则时按以下流程执行：

1. 读取 `fpa_config.yaml`。
2. 解析 `judgement_rules_source`，未配置时默认 `config`。
3. 当来源为 `config`：
   - 读取 `fpa_judgement_rules.yaml`。
   - 校验 `judgement_rules` 必须是非空字符串列表。
   - 返回该列表。
4. 当来源为 `template`：
   - 沿用当前 `_read_fpa_judgement_rules(template_path)` 的 Excel 附录读取逻辑。
5. 若最终列表为空：
   - `config` 来源应报错。
   - `template` 来源可保持当前 warning 行为，提示模板未配置判定原则。

## 拟修改范围

- `ai_gen_reimbursement_docs/config_utils.py`
  - 新增 `FPA_JUDGEMENT_RULES_FILENAME`。
  - 新增 `load_fpa_judgement_rules_source()`。
  - 新增 `load_fpa_judgement_rules_config()`。
  - 扩展 `validate_fpa_config()` 校验 `judgement_rules_source`。

- `ai_gen_reimbursement_docs/gen_fpa.py`
  - 将当前模板读取函数拆分或包装为按来源读取。
  - `plan_fpa_md_from_tree()` 和预览相关路径统一使用来源选择后的判定原则列表。

- `config/fpa_config.yaml.example`
  - 新增 `judgement_rules_source: config`。

- `config/fpa_judgement_rules.yaml.example`
  - 新增默认示例判定原则列表。

- 测试
  - 补充配置读取、来源选择、缺失文件、空列表、非法来源等测试。

## 验收用例

1. 默认未显式配置或配置为 `config` 时，从 `fpa_judgement_rules.yaml` 读取判定原则。
2. 显式配置 `judgement_rules_source: template` 时，仍从 Excel 模板附录读取。
3. `config` 来源下，配置文件缺失时报错。
4. `config` 来源下，`judgement_rules` 为空或不是字符串列表时报错。
5. `judgement_rules_source` 为非法值时报错。
6. AI prompt 中仍能看到编号后的判定原则列表。
7. AI 返回 `classification_basis_index` 后，后处理仍按列表序号映射「计算依据归类」。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_config_utils.py tests/test_gen_fpa_ai.py tests/test_gen_fpa_preview.py
```

若实现影响 pipeline 或 Web 预览配置接口，应追加：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py tests/test_web_tasks.py
```

## 风险与注意事项

- 默认来源改为 `config` 后，用户配置目录必须提供 `fpa_judgement_rules.yaml`，否则 `gen-fpa` 会失败。
- 当前模板读取失败只记录 warning；配置文件来源应更严格，避免后续 AI 生成无法映射的归类。
- Web 预览和正式生成必须共用同一读取逻辑，避免预览与最终 Excel 结果不一致。
- `fpa_config.yaml` 当前是严格校验，新增字段后示例文件、测试夹具和文档需要同步更新。
