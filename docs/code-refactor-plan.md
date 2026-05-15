# 代码重构方案：CLI / Web UI 共享核心

## 动机

当前代码中，from-excel 管道的完整执行逻辑嵌在 `main.py` 的 `main()` 函数里（约 500 行 if/elif），Web UI 必须复制一份调用链。这导致：

1. CLI 和 Web 各自维护一套执行逻辑，容易产生不一致
2. 日志系统在 import 阶段强制初始化，Web 进程被迫接受
3. `os.environ` 全局设置 API Key，多线程不安全
4. import 时有副作用（删 `__pycache__`、初始化 logger）

目标：抽取一个共享的 `pipeline.py`，CLI 和 Web 都只做"参数收集 → 调用 pipeline → 展示结果"。

---

## 1. 现状问题清单

### 1.1 执行逻辑嵌在 main()

**位置**：`main.py` 第 808–1300 行

```python
# main() 中的结构
def main():
    # ... 参数解析、配置加载 ...
    if any([args.gen_basedata, args.gen_fpa, ...]):   # ← 从这里开始 500 行
        _section("Excel 功能清单 → 全套交付物")
        # 路径解析
        # 模板查找
        # 基础数据生成
        # 元数据 AI 填充
        # FPA 生成
        # 需求说明书生成
        # COSMIC 生成
        # 需求清单生成
```

Web UI 的 `server.py` 中 `_execute_excel_mode` 函数复制了这一段。维护时需要两边同步。

### 1.2 os.environ 全局污染

**位置**：`main.py` 第 797–799 行

```python
if api_key:
    os.environ["ANTHROPIC_API_KEY"] = api_key
if base_url:
    os.environ["ANTHROPIC_BASE_URL"] = base_url
```

核心函数（`fill_md_with_ai`、`generate_cosmic_items` 等）已支持 `api_key` 参数传入，不需要全局设置。但在多线程 Web 进程中，`os.environ` 是共享的，存在竞态。

### 1.3 日志在 import 时初始化

**位置**：`main.py` 第 47–91 行，及模块底部

```python
def _init_global_logging():
    logger = logging.getLogger('ai_gen_reimbursement_docs')
    # 添加 FileHandler + StreamHandler
    ...

# 模块加载时执行
logger, run_log = _init_global_logging()
```

Web 进程 import `main` 时也会触发，导致日志自动写到文件和终端，而不是按 Web 会话路由。

### 1.4 import 有副作用

**位置**：`main.py` 第 41–43 行

```python
_pycache = os.path.join(os.path.dirname(__file__), '__pycache__')
if os.path.isdir(_pycache):
    shutil.rmtree(_pycache, ignore_errors=True)
```

每次 `import main` 都删除 `__pycache__`。Web 进程中无意义，还可能误删正在使用的缓存。

### 1.5 Windows 专属调用

**位置**：`main.py` 多处

```python
import winsound                    # 717 行
winsound.PlaySound(...)           # 723 行
os.startfile(log_dir)             # 741 行
os.system(f'tail -f ...')         # 751 行
input("\n按 Enter 键退出...")      # 1287 行
```

Web 进程（可能在 Linux 容器中）调用这些会报错。

### 1.6 路径计算散落各处

```python
# 不同位置，不同逻辑
os.path.dirname(os.path.dirname(__file__))              # 源码模式
os.path.dirname(sys.executable)                         # exe 模式
os.path.expanduser('~/.ai-gen-reimbursement-docs')      # 配置文件
os.path.dirname(os.path.abspath(excel_path))            # 输出目录
```

没有一个统一的方法告诉 pipeline "产物放哪"，Web UI 需要用自己的临时目录覆盖这些。

---

## 2. 目标架构

```
┌──────────┐    ┌──────────┐
│  CLI      │    │  Web UI  │
│  main.py  │    │ server.py│
└─────┬─────┘    └────┬─────┘
      │               │
      │  parse args   │  parse HTTP request
      │  load config  │  load config  
      │               │  setup session log
      │               │
      └───────┬───────┘
              │
    参数收集为 dict / kwargs
              │
              ▼
   ┌─────────────────────┐
   │   pipeline.py       │  ← 新增，~200 行
   │                     │
   │   run_pipeline(     │
   │     mode,           │
   │     file_path,      │
   │     output_dir,     │
   │     api_key,        │
   │     model,          │
   │     base_url,       │
   │     project_name,   │
   │     templates,      │
   │     log_callback,   │  ← Web 传入自己的日志处理
   │   ) -> PipelineResult│
   └─────────┬───────────┘
             │
             │ 调用现有核心函数（传参，不走全局状态）
             │
             ▼
   ┌─────────────────────┐
   │  现有核心模块         │  不变
   │  md_handler         │
   │  excel_writer       │
   │  gen_xlsx           │
   │  gen_spec           │
   │  cosmic_llm         │
   │  excel_source       │
   │  llm_client         │
   └─────────────────────┘
```

---

## 3. 详细改动

### 3.1 新增 `ai_gen_reimbursement_docs/pipeline.py`

**职责**：编排 from-excel 管道，返回产物路径集合。

**签名**：

```python
from dataclasses import dataclass, field
from typing import Callable, Optional

@dataclass
class PipelineResult:
    """管道执行结果"""
    session_id: str                          # 唯一标识
    fpa_xlsx: str = ""                       # FPA 工作量评估路径
    cosmic_xlsx: str = ""                    # 功能点拆分表路径
    require_xlsx: str = ""                   # 需求清单路径
    spec_docx: str = ""                      # 需求说明书路径
    tree_md: str = ""                        # 模块树 MD 路径
    meta_md: str = ""                        # 元数据 MD 路径
    cfp_total: float = 0.0                   # CFP 总和
    fpa_reduced: float = 0.0                 # 核减后工作量
    errors: list[str] = field(default_factory=list)


def run_pipeline(
    *,
    mode: str,                               # 操作模式
    file_path: str,                          # 输入 Excel 路径
    output_dir: str,                         # 产物输出目录
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    project_name: str = "",
    templates: Optional[dict[str, str]] = None,  # {"fpa": path, ...}
    log_callback: Optional[Callable[[str, str], None]] = None,
    # log_callback(level: str, message: str)  ← Web 传入 queue.put
) -> PipelineResult:
    """
    CLI 调用:
      result = run_pipeline(
          mode="gen-all",
          file_path="功能清单.xlsx",
          output_dir="./products/",
          api_key="sk-xxx",
          model="deepseek-v4-flash",
      )

    Web 调用:
      result = run_pipeline(
          mode="gen-all",
          file_path="/tmp/req_abc123/input/功能清单.xlsx",
          output_dir="/tmp/req_abc123/output/",
          api_key="sk-xxx",
          log_callback=lambda level, msg: queue.put(...),
      )
    """
```

**内部调用链**（从 `main()` 搬过来，去掉 CLI 依赖）：

```python
def run_pipeline(*, mode, file_path, output_dir, api_key, model, 
                 base_url, project_name, templates, log_callback):
    
    _log("INFO", f"模式: {mode}, 文件: {os.path.basename(file_path)}")
    
    # 目录准备
    doc_dir = os.path.join(output_dir, 'cosmic文档')
    md_dir = os.path.join(output_dir, 'md')
    os.makedirs(doc_dir, exist_ok=True)
    os.makedirs(md_dir, exist_ok=True)

    # 路径变量
    tree_md = os.path.join(md_dir, 'gen-basedata-功能清单-模块树.md')
    meta_md_tpl = os.path.join(md_dir, 'gen-basedata-录入文档元数据-模板.md')
    meta_filled_md = os.path.join(md_dir, 'gen-basedata-AI填充-录入文档元数据.md')
    fpa_sum_md = os.path.join(md_dir, 'gen-fpa-FPA工作量-总和.md')
    
    result = PipelineResult(session_id=uuid.uuid4().hex[:8])

    # 模板解析
    tpl = templates or {}
    fpa_src = tpl.get('fpa', _default_template('FPA工作量评估-模板'))
    cosmic_src = tpl.get('cosmic', _default_template('项目功能点拆分表-模板'))
    require_src = tpl.get('list', _default_template('项目需求清单-模板'))
    spec_src = tpl.get('spec', _default_template('项目需求说明书-模板'))

    meta_md = meta_filled_md if os.path.exists(meta_filled_md) else meta_md_tpl

    # ── gen-basedata ──
    if mode in ("gen-basedata", "gen-all"):
        _log("INFO", "第0步: 生成数据源中间文件...")
        generate_md_files(file_path, md_dir)
        verify_module_tree_stats(tree_md, meta_md_tpl)
        if api_key and not os.path.exists(meta_filled_md):
            if load_enable_ai_fill_meta():
                _ai_fill_meta_md(meta_md_tpl, meta_filled_md, api_key, model, base_url, tree_md=tree_md)
            else:
                shutil.copy2(meta_md_tpl, meta_filled_md)
        if os.path.exists(meta_filled_md):
            meta_md = meta_filled_md
        result.tree_md = tree_md
        result.meta_md = meta_md
        if mode == "gen-basedata":
            return result

    # 确保基础数据存在
    _ensure_basedata(file_path, md_dir, meta_md, tree_md, meta_md_tpl)
    if api_key and not os.path.exists(meta_filled_md):
        if load_enable_ai_fill_meta():
            _ai_fill_meta_md(meta_md_tpl, meta_filled_md, api_key, model, base_url, tree_md=tree_md)
        else:
            shutil.copy2(meta_md_tpl, meta_filled_md)
    if os.path.exists(meta_filled_md):
        meta_md = meta_filled_md

    # ── gen-fpa ──
    fpa_xlsx = os.path.join(output_dir, 'FPA工作量评估.xlsx')
    if mode in ("gen-fpa", "gen-all"):
        _log("INFO", "第1步: 生成 FPA 工作量评估...")
        fpa_md = os.path.join(md_dir, 'gen-fpa-FPA-模板.md')
        fpa_filled_md = os.path.join(md_dir, 'gen-fpa-AI填充-FPA.md')
        init_fpa_template_md(tree_md, meta_md, fpa_md, summary_md_path=fpa_sum_md)
        if api_key:
            shutil.copy2(fpa_md, fpa_filled_md)
            ai_fill_fpa_md(fpa_filled_md, meta_md, api_key=api_key, model=model, base_url=base_url)
        else:
            fpa_filled_md = fpa_md
        generate_fpa_xlsx_from_md(fpa_filled_md, meta_md, fpa_src, fpa_xlsx)
        result.fpa_xlsx = fpa_xlsx
        result.fpa_reduced = _read_md_value(fpa_sum_md, r'FPA工作量（人/天）[：:]\s*([\d.]+)') or 0.0
        if mode == "gen-fpa":
            return result

    # ── gen-spec ──
    spec_docx = os.path.join(doc_dir, '项目需求说明书.docx')
    if mode in ("gen-spec", "gen-all"):
        _log("INFO", "生成 项目需求说明书...")
        # 复用 meta，但 spec 在 gen-all 中是第2步
        _ensure_meta_for(mode, file_path, md_dir, tree_md, meta_md_tpl, 
                         meta_filled_md, api_key, model, base_url)
        meta_md = meta_filled_md if os.path.exists(meta_filled_md) else meta_md_tpl
        spec_md = os.path.join(md_dir, 'gen-spec-spec-功能需求章节-模板.md')
        spec_filled_md = os.path.join(md_dir, 'gen-spec-AI填充-spec-功能需求章节.md')
        if not os.path.exists(spec_filled_md):
            init_spec_template_md(tree_md, meta_md, spec_md)
            if api_key:
                ai_fill_spec_md(spec_md, spec_filled_md, api_key, model, base_url)
            else:
                shutil.copy2(spec_md, spec_filled_md)
        filled = spec_filled_md if os.path.exists(spec_filled_md) else ""
        generate_spec_docx_from_md(spec_src, spec_docx, meta_md, tree_md, filled_md_path=filled)
        result.spec_docx = spec_docx
        if mode == "gen-spec":
            return result

    # ── gen-cosmic ──
    cosmic_xlsx = os.path.join(doc_dir, '项目功能点拆分表.xlsx')
    if mode in ("gen-cosmic", "gen-all"):
        _log("INFO", "生成 项目功能点拆分表...")
        modules = _build_modules_from_tree_md(tree_md)
        project = _read_project_name(meta_md) or (modules[0].name if modules else "项目")
        init_md_path = os.path.join(md_dir, 'gen-cosmic-cosmic模板.md')
        filled_md_path = os.path.join(md_dir, 'gen-cosmic-AI填充cosmic.md')
        export_empty_md(modules, project, init_md_path)
        if api_key:
            shutil.copy2(init_md_path, filled_md_path)
            _user_cfg = load_user_config_from_meta(meta_md)
            fill_md_with_ai(filled_md_path, modules, project, api_key, model, base_url, **_user_cfg)
            items = parse_md_to_items(filled_md_path)
            if items:
                _meta = _parse_meta_md(meta_md)
                generate_cosmic_xlsx_from_md(cosmic_src, cosmic_xlsx, items, meta=_meta)
                result.cfp_total = sum(item.total_cfp() for item in items)
                _write_cfp_sum(md_dir, result.cfp_total)
                _target = _meta.get("建设目标", "")
                _necessity = _meta.get("建设必要性", "")
                if _target or _necessity:
                    write_environment_sheet(cosmic_xlsx, cosmic_xlsx, project, _target, _necessity)
        result.cosmic_xlsx = cosmic_xlsx
        if mode == "gen-cosmic":
            return result

    # ── gen-list ──
    require_xlsx = os.path.join(doc_dir, '项目需求清单.xlsx')
    if mode in ("gen-list", "gen-all"):
        _log("INFO", "生成 项目需求清单...")
        generate_list_xlsx_from_md(
            meta_md, tree_md, require_src, require_xlsx,
            cfp_total=result.cfp_total, fpa_reduced=result.fpa_reduced
        )
        result.require_xlsx = require_xlsx
        if mode == "gen-list":
            return result

    return result


def _log(level: str, msg: str):
    """统一日志：先走 callback（Web），再走 logger（CLI）"""
    logger = logging.getLogger('ai_gen_reimbursement_docs')
    getattr(logger, level.lower())(msg)

# 如果调用方提供了 log_callback，pipe 模式下需要注入。实际实现中通过
# logging.Handler 或 contextvars 传递，保证现有日志调用无需改动。
```

### 3.2 瘦身 `main.py`

**改动前**（~900 行）：import 副作用 + 7 个死函数 + 500 行编排逻辑

**改动后**（~300 行）：纯 CLI 层

```python
"""AI生成项目报账文档 - CLI入口"""
import argparse
import logging
import os
import sys

from ai_gen_reimbursement_docs.pipeline import run_pipeline, PipelineResult
from ai_gen_reimbursement_docs.config_utils import (
    load_api_key, load_base_url, load_model_name
)


def _build_parser() -> argparse.ArgumentParser:
    """CLI 参数解析器。"""
    parser = argparse.ArgumentParser(
        description="AI生成项目报账文档 — 从功能清单自动生成全套报账交付物",
        ...
    )
    # --api-key, --model, --from-excel, --gen-*, --output-dir, 
    # --project-name, --*-template, --clean, --init-config, --log, 
    # --version, --test-sound, --max-tokens
    return parser


def _setup_cli_logging():
    """CLI 模式：初始化文件 + 控制台日志。"""
    # 从 _init_global_logging 搬过来，只在 CLI 入口调用
    ...


def main():
    """CLI 入口：解析参数 → 调用 pipeline → 输出结果。"""
    _setup_cli_logging()
    
    parser = _build_parser()
    args = parser.parse_args()
    
    # ... version, init-config, log-viewer 等纯 CLI 功能 ...
    
    if any([args.gen_basedata, args.gen_fpa, args.gen_cosmic, 
            args.gen_list, args.gen_spec, args.gen_all]):
        
        # 解析参数
        mode = _resolve_mode(args)
        output_dir = args.output_dir or _auto_output_dir(args.from_excel, args.project_name)
        templates = _parse_template_args(args)
        
        # 调用共享 pipeline
        result = run_pipeline(
            mode=mode,
            file_path=args.from_excel,
            output_dir=output_dir,
            api_key=args.api_key or load_api_key(),
            model=args.model or load_model_name(),
            base_url=load_base_url(),
            project_name=args.project_name,
            templates=templates,
        )
        
        # 展示结果
        _print_result(result)


if __name__ == '__main__':
    main()
```

### 3.3 修复 `os.environ` 污染

**改动**：`main.py` 删除这两行，`pipeline.py` 不设 `os.environ`。

```python
# 删除（main.py:797-799）
os.environ["ANTHROPIC_API_KEY"] = api_key
os.environ["ANTHROPIC_BASE_URL"] = base_url
```

所有核心函数已接受 `api_key`、`model`、`base_url` 参数，不需要通过环境变量传递。

### 3.4 日志解耦

**现状**：

```python
# main.py，模块加载时执行
logger, run_log = _init_global_logging()
```

**改后**：

```python
# main.py：CLI 入口函数内调用
def main():
    _setup_cli_logging()  # 只在 CLI 进程执行
    ...

# pipeline.py：不初始化 handler，仅使用 getLogger
_logger = logging.getLogger('ai_gen_reimbursement_docs')

# web_app/server.py：自己挂 SessionHandler
parent = logging.getLogger('ai_gen_reimbursement_docs')
parent.addHandler(SessionHandler())
```

`_init_global_logging()` 函数**保留**但移到 `main()` 内调用，不再在 import 时执行。

### 3.5 移除 import 副作用

**删除**：

```python
# main.py 第 41-43 行
_pycache = os.path.join(os.path.dirname(__file__), '__pycache__')
if os.path.isdir(_pycache):
    shutil.rmtree(_pycache, ignore_errors=True)
```

### 3.6 Windows 专属调用隔离

| 调用 | 位置 | 处理 |
|------|------|------|
| `winsound.PlaySound` | `main.py:723` | 保留在 `main()` 的 `--test-sound` 处理中，不进入 pipeline |
| `os.startfile(log_dir)` | `main.py:741` | 保留在 CLI log viewer 中 |
| `os.system('tail -f')` | `main.py:751` | 保留在 CLI log viewer 中 |
| `input("按 Enter 键退出")` | `main.py:1287` | 保留在 `if __name__ == '__main__'` 块中 |

这些都不需要移入 `pipeline.py`。

### 3.7 Web UI 的 server.py 简化

**改动前**（~700 行）：包含 150 行 `_execute_excel_mode` 复制实现

**改动后**（~500 行）：

```python
from ai_gen_reimbursement_docs.pipeline import run_pipeline, PipelineResult

@app.post("/api/run")
async def api_run(file: UploadFile, mode: str, ...):
    session_id = uuid.uuid4().hex[:8]
    work_dir = Path(tempfile.mkdtemp(prefix=f"ard_web_{session_id}_"))
    
    # 保存上传文件
    input_path = work_dir / 'input' / file.filename
    input_path.write_bytes(await file.read())
    
    # 保存自定义模板
    templates = {}
    if fpa_template:
        tp = work_dir / 'templates' / 'FPA模板.xlsx'
        tp.write_bytes(await fpa_template.read())
        templates['fpa'] = str(tp)
    # ... 其他模板同理
    
    output_dir = work_dir / 'output'
    
    # 日志队列
    log_queue = queue.Queue(maxsize=500)
    session_queues[session_id] = log_queue
    
    def run():
        session_var.set(session_id)
        try:
            result = run_pipeline(      # ← 直接调共享函数
                mode=mode,
                file_path=str(input_path),
                output_dir=str(output_dir),
                api_key=api_key,
                model=model,
                base_url=base_url,
                templates=templates,
            )
            # 打包产物 ZIP
            shutil.make_archive(str(work_dir / f'产物_{session_id}'), 'zip', str(output_dir))
        except Exception as e:
            logger.error(f"执行失败: {e}")
        finally:
            log_queue.put(json.dumps({"level": "DONE"}))
    
    asyncio.create_task(asyncio.to_thread(run))
    return {"session_id": session_id}
```

---

## 4. 文件变更汇总

| 文件 | 操作 | 行数变化 | 说明 |
|------|------|---------|------|
| `pipeline.py` | **新增** | +200 | 共享执行编排 |
| `main.py` | 重写 | -600, +100 | 瘦身为纯 CLI 层 |
| `web_app/server.py` | 简化 | -150 | 调用 pipeline 代替自实现 |
| `md_handler.py` | 不变 | 0 | — |
| `cosmic_llm.py` | 不变 | 0 | — |
| `excel_writer.py` | 不变 | 0 | — |
| `gen_xlsx.py` | 不变 | 0 | — |
| `gen_spec.py` | 不变 | 0 | — |
| `excel_source.py` | 不变 | 0 | — |
| `config_utils.py` | 不变 | 0 | — |
| `llm_client.py` | 不变 | 0 | — |

**净变化**：+200 行（pipeline.py），-650 行（main.py）+ 简化 server.py

---

## 5. 执行步骤

### Step 1：新建 `pipeline.py`

- [ ] 从 `main.py` 的 `--gen-all` 块提取完整调用链
- [ ] 封装为 `run_pipeline()` 函数，所有参数 keyword-only
- [ ] 每个子模式独立返回，依赖链式检查
- [ ] 返回 `PipelineResult` 数据类
- [ ] 不调用 `os.environ`、不初始化日志 handler

### Step 2：重构 `main.py`

- [ ] 删除 import 时执行的 `_init_global_logging()` 调用
- [ ] 将日志初始化移入 `main()` 函数
- [ ] 删除 `os.environ` 设置
- [ ] 用 `run_pipeline()` 替换 808–1300 行的编排逻辑
- [ ] 保留纯 CLI 功能（log viewer、init-config、version、test-sound）

### Step 3：更新 `web_app/server.py`

- [ ] 删除 `_execute_excel_mode`、`_execute_docx_mode`、`_execute_mode`
- [ ] 替换为 `run_pipeline()` 调用

### Step 4：测试

- [ ] CLI：`ard --from-excel 功能清单.xlsx --gen-all`
- [ ] CLI：分步模式逐一测试
- [ ] Web：上传文件 → 全套 → 下载
- [ ] Web：两个浏览器同时请求，日志不串
- [ ] 全量单元测试：`pytest tests/`

---

## 6. 风险与注意事项

- `_ensure_basedata`、`_ai_fill_meta_md` 等函数目前是 `main.py` 模块级私有函数，需确认直接 import 或改为 pipeline 内部实现
- `_read_project_name`、`_parse_meta_md` 等目前定义在 `main.py` 和 `gen_spec.py` 中，pipeline 需统一引用
- 模板路径解析 `_tpl()` 逻辑（优先级：CLI > Sheet 8 > 默认）需要在 pipeline 中体现
- `--clean` 和 `--project-name` 对输出目录的影响需要在 CLI 层处理完再传给 pipeline
