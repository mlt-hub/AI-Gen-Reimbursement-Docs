# 代码重构方案 v2：抽取共享 Pipeline

## 目标

将 `main.py` 中嵌入的 from-excel 管道执行逻辑抽取为独立的 `pipeline.py`，使 CLI 和未来的 Web UI 共用同一套调用链。

**本方案范围**：仅重构 CLI 侧，不涉及 Web UI 实现。

---

## 1. 当前问题

### 1.1 编排逻辑嵌在 main() 里

`main.py` 的 `main()` 函数约 500 行，结构如下：

```
main()
  ├─ 参数解析 (_build_parser)
  ├─ 日志查看 (--log)
  ├─ 版本 (--version)
  ├─ 初始化配置 (--init-config)
  ├─ 配置加载 + os.environ 设置
  └─ from-excel 管道 (--gen-*)     ← 约 450 行，嵌在 if/elif 中
       ├─ 路径解析 (20行)
       ├─ 模板查找 (30行)
       ├─ gen-basedata 逻辑 (40行)
       ├─ gen-fpa 逻辑 (40行)
       ├─ gen-spec 逻辑 (40行)
       ├─ gen-cosmic 逻辑 (50行)
       ├─ gen-list 逻辑 (20行)
       └─ gen-all 全流程 (200行，重复上述子步骤)
```

做 Web UI 时必须把这一段复制过去，之后每改一个 bug 都要两边同步。

### 1.2 全局状态污染

```python
# main.py:797-799
os.environ["ANTHROPIC_API_KEY"] = api_key
os.environ["ANTHROPIC_BASE_URL"] = base_url
```

核心函数已支持 `api_key` 参数传入，不需要设置环境变量。多线程场景下是竞态。

### 1.3 import 副作用

```python
# main.py:41-43 — import 时自动删除 __pycache__
_pycache = os.path.join(os.path.dirname(__file__), '__pycache__')
if os.path.isdir(_pycache):
    shutil.rmtree(_pycache, ignore_errors=True)

# main.py:91 — import 时初始化全局日志 handler
logger, run_log = _init_global_logging()
```

任何 `import main` 的代码都会触发，不受控制。

### 1.4 配置加载和业务逻辑混杂

`main()` 中 API Key 读取、配置迁移、模板路径优先级判断、输出目录计算全部内联在同一个函数里，没有清晰的边界。

---

## 2. 目标结构

```
main.py  (瘦身为纯 CLI 层，~300 行)
  │
  ├─ 参数解析
  ├─ 配置加载
  ├─ CLI 专属功能 (--log, --version, --init-config)
  └─ 调用 ──────────┐
                    ▼
pipeline.py  (新增，~200 行)
  │
  ├─ run_pipeline()          ← 总入口，模式分发
  ├─ _gen_basedata()         ← 第0步
  ├─ _gen_fpa()              ← 第1步
  ├─ _gen_cosmic()           ← 第2步
  ├─ _gen_list()             ← 第3步
  ├─ _gen_spec()             ← 需求说明书
  └─ _gen_all()              ← 全流程串联
         │
         ▼
现有核心模块 (不变)
  md_handler, excel_writer, gen_xlsx, gen_spec, cosmic_llm, excel_source
```

---

## 3. pipeline.py 设计

### 3.1 返回值

```python
from dataclasses import dataclass, field

@dataclass
class PipelineResult:
    """管道执行结果，各字段在对应步骤完成后填充"""
    # 中间产物
    tree_md: str = ""
    meta_md: str = ""
    # 最终产物
    fpa_xlsx: str = ""
    cosmic_xlsx: str = ""
    require_xlsx: str = ""
    spec_docx: str = ""
    # 统计值
    cfp_total: float = 0.0
    fpa_reduced: float = 0.0
    # 错误
    errors: list[str] = field(default_factory=list)
```

### 3.2 总入口

```python
def run_pipeline(
    *,
    mode: str,                     # "gen-all" | "gen-fpa" | "gen-cosmic" | "gen-list" | "gen-spec" | "gen-basedata"
    file_path: str,                # 输入 Excel 路径（必须存在）
    output_dir: str,               # 产物输出目录（自动创建）
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    project_name: str = "",        # 优先用此值，为空则从 Excel 自动读取
    templates: dict[str, str] | None = None,  # {"fpa": path, "cosmic": path, ...}
) -> PipelineResult:
```

所有参数 keyword-only，调用方清晰知道传了什么。

### 3.3 内部实现要点

```python
def run_pipeline(*, mode, file_path, output_dir, api_key, model, base_url,
                 project_name, templates):
    
    logger = logging.getLogger('ai_gen_reimbursement_docs.pipeline')
    
    # 校验输入
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"输入文件不存在: {file_path}")
    if mode not in VALID_MODES:
        raise ValueError(f"未知模式: {mode}")
    
    # 准备目录
    os.makedirs(output_dir, exist_ok=True)
    doc_dir = os.path.join(output_dir, 'cosmic文档')
    md_dir = os.path.join(output_dir, 'md')
    os.makedirs(doc_dir, exist_ok=True)
    os.makedirs(md_dir, exist_ok=True)
    
    # 模板解析（优先级：传入 > Sheet 8 > 默认目录）
    tpl = _resolve_templates(file_path, templates)
    
    result = PipelineResult()
    
    # ── 模式分发 ──
    if mode == "gen-all":
        return _gen_all(
            file_path, output_dir, doc_dir, md_dir, tpl,
            api_key, model, base_url, result
        )
    
    if mode == "gen-basedata":
        _ensure_basedata(file_path, md_dir, result)
        _ensure_meta_filled(md_dir, api_key, model, base_url, result)
        return result
    
    # 其他单步模式需要先确保基础数据
    _ensure_basedata(file_path, md_dir, result)
    _ensure_meta_filled(md_dir, api_key, model, base_url, result)
    
    if mode == "gen-fpa":
        return _gen_fpa(file_path, output_dir, md_dir, tpl,
                        api_key, model, base_url, result)
    if mode == "gen-cosmic":
        return _gen_cosmic(file_path, doc_dir, md_dir, tpl,
                           api_key, model, base_url, result)
    if mode == "gen-list":
        return _gen_list(doc_dir, md_dir, tpl, result)
    if mode == "gen-spec":
        return _gen_spec(file_path, doc_dir, md_dir, tpl,
                         api_key, model, base_url, result)
```

### 3.4 各子函数签名

```python
def _gen_basedata(
    file_path: str, md_dir: str, result: PipelineResult
) -> PipelineResult:
    """第0步：生成功能清单模块树.md + 录入文档元数据-模板.md"""
    ...

def _gen_fpa(
    file_path: str, output_dir: str, md_dir: str,
    tpl: dict, api_key: str, model: str, base_url: str,
    result: PipelineResult
) -> PipelineResult:
    """第1步：FPA 工作量评估"""
    ...

def _gen_cosmic(
    file_path: str, doc_dir: str, md_dir: str,
    tpl: dict, api_key: str, model: str, base_url: str,
    result: PipelineResult
) -> PipelineResult:
    """第2步：COSMIC 功能点拆分表"""
    ...

def _gen_list(
    doc_dir: str, md_dir: str, tpl: dict,
    result: PipelineResult
) -> PipelineResult:
    """第3步：需求清单"""
    ...

def _gen_spec(
    file_path: str, doc_dir: str, md_dir: str,
    tpl: dict, api_key: str, model: str, base_url: str,
    result: PipelineResult
) -> PipelineResult:
    """需求说明书（无固定顺序依赖）"""
    ...

def _gen_all(
    file_path: str, output_dir: str, doc_dir: str, md_dir: str,
    tpl: dict, api_key: str, model: str, base_url: str,
    result: PipelineResult
) -> PipelineResult:
    """全流程：base → fpa → spec → cosmic → list（按 main.py 现有顺序）"""
    ...
```

### 3.5 辅助函数

```python
def _resolve_templates(file_path: str, cli_templates: dict | None) -> dict:
    """解析模板路径，优先级：CLI 参数 > Excel Sheet 8 > data/templates/"""
    tpl_cfg = read_template_config(file_path)  # 读 Sheet 8
    templates = {}
    for key, sheet_key, default_name in [
        ('fpa',    'FPA工作量评估-模板',     'FPA工作量评估-模板.xlsx'),
        ('cosmic', '项目功能点拆分表-模板',   '项目功能点拆分表-模板.xlsx'),
        ('list',   '项目需求清单-模板',       '项目需求清单-模板.xlsx'),
        ('spec',   '项目需求说明书-模板',     '项目需求说明书-模板.docx'),
    ]:
        # 1. CLI 传入
        if cli_templates and key in cli_templates:
            templates[key] = cli_templates[key]
            continue
        # 2. Sheet 8
        cfg_path = tpl_cfg.get(sheet_key, '')
        if cfg_path and os.path.exists(cfg_path):
            templates[key] = cfg_path
            continue
        # 3. 默认
        default = os.path.join(_project_root(), 'data', 'templates', default_name)
        if os.path.exists(default):
            templates[key] = default
    return templates


def _find_output_dir(excel_path: str, cli_output_dir: str, 
                     cli_project_name: str) -> str:
    """确定输出目录。"""
    if cli_output_dir:
        return cli_output_dir
    excel_dir = os.path.dirname(os.path.abspath(excel_path))
    project = cli_project_name or _read_project_name_from_excel(excel_path) or 'products'
    safe_name = re.sub(r'[\/:*?"<>|]', '_', project)
    return os.path.join(excel_dir, safe_name)
```

---

## 4. main.py 改动

### 4.1 删除的内容

| 行范围（现行） | 内容 | 原因 |
|-------------|------|------|
| 41-43 | `rmtree(__pycache__)` | import 副作用 |
| 61-91 | `_init_global_logging()` 在模块级调用 | import 副作用 |
| 808-1300 | `main()` 中的 from-excel 编排逻辑 | 移至 pipeline.py |

### 4.2 修改的内容

```python
# 模块顶部 — 不再在 import 时执行副作用
# （删除 rmtree 和 _init_global_logging() 调用）


def _setup_cli_logging():
    """CLI 模式日志初始化，只在 main() 中调用。"""
    # 从原 _init_global_logging 搬过来
    log_dir = os.path.join(...)
    logger = logging.getLogger('ai_gen_reimbursement_docs')
    # ... file handler, console handler ...


def main():
    _setup_cli_logging()  # ← 移到函数内
    
    parser = _build_parser()
    args = parser.parse_args()
    
    # ... --version, --init-config, --log, --test-sound 等保持不变 ...
    
    # 配置加载
    api_key = args.api_key or load_api_key()
    model = args.model or load_model_name()
    base_url = load_base_url()
    # 删除 os.environ["ANTHROPIC_API_KEY"] = api_key
    
    # from-excel 管道
    if any([args.gen_basedata, args.gen_fpa, args.gen_cosmic,
            args.gen_list, args.gen_spec, args.gen_all]):
        
        mode = _resolve_mode(args)
        output_dir = args.output_dir or _find_output_dir(
            args.from_excel, args.output_dir, args.project_name
        )
        templates = {
            k: getattr(args, v, '') 
            for k, v in [('fpa', 'fpa_out_template'), 
                         ('cosmic', 'cosmic_out_template'),
                         ('list', 'list_out_template'), 
                         ('spec', 'spec_out_template')]
            if getattr(args, v, '')
        } or None
        
        result = run_pipeline(
            mode=mode,
            file_path=args.from_excel,
            output_dir=output_dir,
            api_key=api_key,
            model=model,
            base_url=base_url,
            project_name=args.project_name,
            templates=templates,
        )
        
        # 输出结果摘要
        for label, path in [
            ("FPA 工作量评估", result.fpa_xlsx),
            ("项目功能点拆分表", result.cosmic_xlsx),
            ("项目需求清单", result.require_xlsx),
            ("项目需求说明书", result.spec_docx),
        ]:
            if path and os.path.exists(path):
                size = os.path.getsize(path)
                print(f"  ✅ {label}: {path} ({size/1024:.0f} KB)")
        
        if result.errors:
            for e in result.errors:
                print(f"  ⚠️  {e}")
```

### 4.3 保留在 main.py 的内容（不动）

| 函数 | 原因 |
|------|------|
| `_build_parser()` | CLI 专属 |
| `_get_version()` | CLI 专属 |
| `_section()` | CLI 日志格式化 |
| `_play_notify_sound()` | CLI 专属 |
| `--log` 查看器 | CLI 专属 |
| `--init-config` | CLI 专属 |
| `--test-sound` | CLI 专属 |
| `--version` | CLI 专属 |
| `_project_root()` | 被多处引用 |
| `_write_cfp_sum()` | 被 pipeline 引用，可保留或移入 pipeline |
| `_read_md_value()` | 被 pipeline 引用，可保留或移入 pipeline |
| `_resolve_fpa_sum()` | 被 pipeline 引用 |
| `_ensure_basedata()` | 被 pipeline 引用 |
| `_ai_fill_meta_md()` | 被 pipeline 引用 |
| `_build_modules_from_tree_md()` | 被 pipeline 引用 |
| `_read_project_name()` | 被 pipeline 引用 |

> 这些被 pipeline 引用的辅助函数可以保持原位置（`from main import _xxx`），或一并移入 `pipeline.py` 作为模块私有函数。

---

## 5. 文件变更

| 文件 | 操作 | 行数 | 说明 |
|------|------|------|------|
| `pipeline.py` | 新增 | ~250 | 共享执行层 |
| `main.py` | 修改 | -500, +50 | 瘦身为 CLI 层 |
| 其他模块 | 不变 | 0 | — |

---

## 6. 执行步骤

### Step 1：新建 `pipeline.py`

- 从 `main.py` 复制 `gen-all`、`gen-fpa`、`gen-cosmic`、`gen-list`、`gen-spec`、`gen-basedata` 各段逻辑
- 封装为独立函数，每个函数接收文件路径、输出目录等参数，不依赖 `args` Namespace
- 所有 AI 调用的 `api_key`、`model`、`base_url` 通过参数传入，不读 `os.environ`
- 返回值统一为 `PipelineResult`

### Step 2：重构 `main.py`

- 删除 import 副作用（`rmtree __pycache__`、模块级 `_init_global_logging()`）
- 将日志初始化移入 `main()` 内
- 删除 `os.environ["ANTHROPIC_API_KEY"]` 设置
- `main()` 中的 from-excel 块替换为解析 args → 调用 `run_pipeline()` → 输出结果
- 删除已被 pipeline 替代的旧代码

### Step 3：处理辅助函数的归属

- `_write_cfp_sum`、`_read_md_value`、`_ensure_basedata`、`_ai_fill_meta_md`、`_build_modules_from_tree_md`、`_read_project_name`、`_resolve_fpa_sum` — 这些被 pipeline 和 main 共用的函数，统一在 `main.py` 中保留原位置，pipeline 通过 `from main import` 引用

### Step 4：验证

- CLI 全流程：`ard --from-excel 功能清单.xlsx --gen-all`
- CLI 分步：每个 `--gen-*` 单独执行
- 单元测试：`pytest tests/`（121 项全通过）
- 不同输出目录、不同模板参数组合

---

## 7. 不改的内容

| 内容 | 原因 |
|------|------|
| `config_utils.py` | 配置加载逻辑独立，没问题 |
| `md_handler.py` | 只做 Markdown 处理，没问题 |
| `cosmic_llm.py` | 只做 AI 调用，已接受参数传入 |
| `excel_writer.py` | 只做 Excel 写入 |
| `gen_xlsx.py` / `gen_spec.py` | 生成逻辑独立 |
| `excel_source.py` | 数据源生成独立 |
| 日志系统的 `contextvars` 改造 | 属于 Web UI 配套，不在此方案范围 |
