# Web UI 套壳方案

## 1. 概述

为现有 CLI 工具 `ai-gen-reimbursement-docs` 添加 Web 界面，用户通过浏览器上传文件、配置参数、选择操作模式，实时查看日志，下载生成产物。

### 核心原则

- **零侵入**：不修改 `ai_gen_reimbursement_docs/` 下任何文件
- **可并存**：Web 和 CLI 各自独立进程，同时使用互不影响
- **多用户**：支持 3-5 人同时使用，日志和文件完全隔离

### 技术栈

| 层 | 选择 | 原因 |
|---|---|---|
| Web 框架 | FastAPI | 异步、原生 SSE、文件上传简单 |
| 前端 | 单 HTML + vanilla JS + CSS | 无构建工具、无 npm、开箱即用 |
| 并发 | `asyncio.to_thread` + 线程池 | 同步 AI 调用放线程池，不阻塞事件循环 |
| 日志隔离 | `contextvars` + 自定义 Handler | 日志按会话路由到不同 SSE 连接 |
| 存储 | `tempfile.mkdtemp()` | 每个请求独立临时目录，产物打包 ZIP |

---

## 2. 文件结构

```
ai_cosmic/                          # 现有项目，不动
├── ai_gen_reimbursement_docs/      # 现有核心代码（零修改）
├── data/templates/                 # 现有模板（只读共享）
├── config/                         # 现有配置
├── web_app/                        # 新增：Web 壳（两个文件）
│   ├── server.py                   # FastAPI 入口，约 250 行
│   └── static/
│       └── index.html              # 单页面 UI，约 300 行
└── pyproject.toml                  # 新增两个依赖
```

### 新增依赖

```toml
# pyproject.toml 的 dependencies 添加
"fastapi>=0.110.0",
"uvicorn[standard]>=0.27.0",
"python-multipart>=0.0.9",
```

---

## 3. 架构

```
浏览器                           FastAPI                          现有核心
──────                         ──────────                        ──────────
│                                                                           
│  GET /                        返回 index.html                              
│ ──────────────────────────────────────────────────────────────→            
│                                                                           
│  POST /api/run                                                             
│  (上传文件+参数)                                                             
│ ───────────────────────────→  1. 保存文件到 /tmp/req_{session}/             
│                               2. session_var.set(session_id)               
│                               3. asyncio.to_thread(run_pipeline)            
│                               4. run_pipeline 调用现有函数:                  
│                                  fill_md_with_ai(...) ──────────→          
│                                  generate_cosmic_xlsx_from_md(...) ──→     
│                               5. 打包产物 ZIP                               
│                               6. 返回 FileResponse(zip)                    
│ ←───────────────────────────                                               │
│                                                                           
│  GET /api/log-stream?session=xxx                                           
│ ───────────────────────────→  SSE 推送该 session 的日志队列                 
│ ←─ data: 日志行1                                                            
│ ←─ data: 日志行2                                                            
│ ←─ data: [DONE]                                                             
│                                                                           
```

---

## 4. API 设计

### 4.1 GET `/`

返回前端页面。

### 4.2 POST `/api/run`

**请求**（multipart/form-data）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | file | 是 | .xlsx 功能清单文件 |
| `mode` | string | 是 | 操作模式，见下表 |
| `api_key` | string | 否 | Anthropic API Key，不填则用系统配置 |
| `model` | string | 否 | 模型名，默认 `deepseek-v4-flash` |
| `base_url` | string | 否 | API 端点，默认用系统配置 |
| `fpa_template` | file | 否 | 自定义 FPA 模板 |
| `cosmic_template` | file | 否 | 自定义 COSMIC 模板 |
| `list_template` | file | 否 | 自定义需求清单模板 |
| `spec_template` | file | 否 | 自定义需求说明书模板 |

**操作模式**（仅支持 from-excel 流程）：

| mode 值 | 对应 CLI | 输入文件类型 |
|---------|----------|-------------|
| `from-excel-gen-all` | `--from-excel x.xlsx --gen-all` | .xlsx |
| `from-excel-gen-basedata` | `--from-excel x.xlsx --gen-basedata` | .xlsx |
| `from-excel-gen-fpa` | `--from-excel x.xlsx --gen-fpa` | .xlsx |
| `from-excel-gen-cosmic` | `--from-excel x.xlsx --gen-cosmic` | .xlsx |
| `from-excel-gen-list` | `--from-excel x.xlsx --gen-list` | .xlsx |
| `from-excel-gen-spec` | `--from-excel x.xlsx --gen-spec` | .xlsx |

> 注：`--docx` 管道（Word → COSMIC 拆分表）在当前代码中已有调用但缺少函数定义（`convert_to_md`、`get_project_name_from_md` 不存在），暂不支持。

**响应**：

- 成功：返回 `application/zip`，文件名 `产物_{时间戳}.zip`
- 失败：返回 `application/json`，`{"error": "错误信息"}`

**流程**：

```
POST /api/run
  │
  ├─ 生成 session_id (uuid4 前8位)
  ├─ 创建 /tmp/ard_web_{session}/
  │   ├─ input/    ← 上传的文件放这里
  │   ├─ output/   ← 产物输出到这里
  │   └─ custom_templates/  ← 自定义模板（如有）
  │
  ├─ 设置 contextvars.session_id
  ├─ asyncio.to_thread(pipeline, ...)
  │   ├─ 根据 mode 调用现有函数
  │   └─ 产物写入 output/
  │
  ├─ shutil.make_archive(output/, 'zip')
  └─ 返回 FileResponse，返回后清理临时目录
```

### 4.3 GET `/api/log-stream?session=xxx`

SSE 端点，推送指定 session 的实时日志。

**事件格式**：

```
data: {"level": "INFO", "msg": "正在AI填充 12 个模块...", "time": "14:30:01"}

data: {"level": "DEBUG", "msg": "API调用完成", "time": "14:30:15"}

data: {"level": "DONE"}
```

前端连接此端点后持续接收日志，收到 `DONE` 后断开。

---

## 5. 日志隔离机制

### 5.1 问题

现有所有模块使用 `logging.getLogger('ai_gen_reimbursement_docs.xxx')`，日志传播到全局父 logger。多用户同时使用时，需要按会话隔离。

### 5.2 方案：contextvars + 自定义 Handler

```python
# server.py 核心代码

import contextvars
import logging
import queue
import json

# 每个线程/协程独立的会话 ID
session_var: contextvars.ContextVar[str | None] = contextvars.ContextVar('session_id', default=None)

# 全局字典：session_id → Queue
session_queues: dict[str, queue.Queue] = {}

class SessionHandler(logging.Handler):
    """将日志路由到对应 session 的队列"""
    def emit(self, record):
        sid = session_var.get()
        if sid and sid in session_queues:
            msg = {
                "level": record.levelname,
                "msg": self.format(record),
                "time": record.created  # 前端自行格式化
            }
            session_queues[sid].put(json.dumps(msg, ensure_ascii=False))

# 启动时追加到父 logger
parent = logging.getLogger('ai_gen_reimbursement_docs')
handler = SessionHandler()
handler.setLevel(logging.DEBUG)
parent.addHandler(handler)  # 追加，不替换原有 handler
```

### 5.3 工作流程

```
请求进入 → session_var.set('abc123')
                │
现有代码 logger.info("正在填充...")
                │
父 logger 分发到所有 handler
                ├─→ 原有 FileHandler    → 全局日志文件（不变）
                ├─→ 原有 StreamHandler  → 控制台（不变）
                └─→ SessionHandler      → session_queues['abc123']
                                              │
                                    SSE 端点取出 → 推给对应浏览器
```

---

## 6. 前端页面

### 6.1 布局

```
┌──────────────────────────────────────────────────────┐
│  🤖 AI 报账文档生成器                    v5.0.0       │
├──────────────────────┬───────────────────────────────┤
│  📋 配置              │  📄 实时日志                   │
│                      │                               │
│  操作模式             │  ┌──────────────────────────┐ │
│  [下拉选择        ▾] │  │ 14:30:01  解析模块...     │ │
│                      │  │ 14:30:05  AI 填充中...    │ │
│  上传文件             │  │ 14:30:20  生成 Excel ✓   │ │
│  [选择文件         ] │  │ 14:30:21  打包完成        │ │
│  已选: 功能清单.xlsx  │  │ 14:30:22  ── 完成 ──     │ │
│                      │  └──────────────────────────┘ │
│  ── 高级选项 ──      │                               │
│  API Key              │  状态: ● 运行中               │
│  [··············  ]  │                               │
│  模型                 │  📦 产物                      │
│  [deepseek-v4-flash] │  [⬇ 下载产物.zip]             │
│  自定义端点            │                               │
│  [留空用默认        ] │                               │
│                      │                               │
│  [▶ 开始生成]         │                               │
│                      │                               │
└──────────────────────┴───────────────────────────────┘
```

### 6.2 交互逻辑

```
1. 用户选择 mode、上传 file、填写 API Key
2. 点击 [开始生成]
3. 前端 POST /api/run → 拿到 session_id
4. 前端 GET /api/log-stream?session=xxx → 建立 SSE 连接
5. 日志实时显示在右侧面板
6. 收到 DONE → 下载按钮激活，自动下载 ZIP
7. 面板状态: ● 运行中 → ✓ 完成（绿色）/ ✗ 失败（红色）
```

### 6.3 技术细节

- 纯 HTML + CSS + vanilla JS，无框架
- 使用 `EventSource` 接收 SSE
- 使用 `fetch` + `FormData` 上传
- 模式描述通过 JS 字典映射（操作模式 ↔ 说明文案 ↔ 接受的文件类型）

---

## 7. server.py 完整结构

```python
"""
Web UI for ai-gen-reimbursement-docs.
启动: python -m uvicorn web_app.server:app --host 0.0.0.0 --port 8080
"""

import asyncio
import contextvars
import json
import logging
import os
import queue
import shutil
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# ── 日志隔离 ──────────────────────────────────────────

session_var: contextvars.ContextVar[str | None] = contextvars.ContextVar('session_id', default=None)
session_queues: dict[str, queue.Queue] = {}

class SessionHandler(logging.Handler):
    def emit(self, record):
        sid = session_var.get()
        if sid and sid in session_queues:
            msg = json.dumps({
                "level": record.levelname,
                "msg": self.format(record),
                "time": datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
            }, ensure_ascii=False)
            try:
                session_queues[sid].put_nowait(msg)
            except queue.Full:
                pass

# 追加 handler 到 ai_gen_reimbursement_docs 父 logger
_parent = logging.getLogger('ai_gen_reimbursement_docs')
_parent.addHandler(SessionHandler())

# ── 常量 ──────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / 'data' / 'templates'
MODE_INFO = {
    "from-excel-gen-all":     {"label": "Excel → 全套交付物",           "ext": ".xlsx"},
    "from-excel-gen-basedata":{"label": "Excel → 功能清单模块树+元数据", "ext": ".xlsx"},
    "from-excel-gen-fpa":     {"label": "Excel → FPA 工作量评估",      "ext": ".xlsx"},
    "from-excel-gen-cosmic":  {"label": "Excel → COSMIC 拆分表",       "ext": ".xlsx"},
    "from-excel-gen-list":    {"label": "Excel → 需求清单",            "ext": ".xlsx"},
    "from-excel-gen-spec":    {"label": "Excel → 需求说明书",           "ext": ".xlsx"},
}

# ── FastAPI App ────────────────────────────────────────

app = FastAPI(title="AI 报账文档生成器")

static_dir = Path(__file__).parent / 'static'
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def index():
    html = (Path(__file__).parent / 'static' / 'index.html').read_text(encoding='utf-8')
    return HTMLResponse(html)

# ── 核心 API ──────────────────────────────────────────

@app.post("/api/run")
async def api_run(
    file: UploadFile = File(...),
    mode: str = Form(...),
    api_key: str = Form(""),
    model: str = Form(""),
    base_url: str = Form(""),
    fpa_template: UploadFile | None = File(None),
    cosmic_template: UploadFile | None = File(None),
    list_template: UploadFile | None = File(None),
    spec_template: UploadFile | None = File(None),
):
    # 1. 校验
    if mode not in MODE_INFO:
        raise HTTPException(400, f"未知模式: {mode}")

    # 2. 创建独立工作目录
    session_id = uuid.uuid4().hex[:8]
    work_dir = Path(tempfile.mkdtemp(prefix=f"ard_web_{session_id}_"))
    input_dir = work_dir / 'input'
    output_dir = work_dir / 'output'
    custom_t_dir = work_dir / 'custom_templates'
    for d in [input_dir, output_dir, custom_t_dir]:
        d.mkdir(parents=True)

    # 3. 保存上传文件
    file_path = input_dir / file.filename
    content = await file.read()
    file_path.write_bytes(content)

    # 4. 保存自定义模板
    for tpl_file, tpl_name in [
        (fpa_template, 'FPA工作量评估-模板.xlsx'),
        (cosmic_template, '项目功能点拆分表-模板.xlsx'),
        (list_template, '项目需求清单-模板.xlsx'),
        (spec_template, '项目需求说明书-模板.docx'),
    ]:
        if tpl_file is not None:
            tpl_content = await tpl_file.read()
            (custom_t_dir / tpl_name).write_bytes(tpl_content)

    # 5. 准备日志队列
    log_queue: queue.Queue = queue.Queue(maxsize=500)
    session_queues[session_id] = log_queue

    # 6. 在线程池中执行
    def run():
        session_var.set(session_id)
        try:
            _execute_mode(mode, file_path, output_dir, custom_t_dir,
                         api_key, model, base_url)
        except Exception as e:
            logging.getLogger('ai_gen_reimbursement_docs').error(f"执行失败: {e}")
        finally:
            log_queue.put(json.dumps({"level": "DONE"}, ensure_ascii=False))
            session_var.set(None)

    asyncio.create_task(asyncio.to_thread(run))

    return {"session_id": session_id}

@app.get("/api/log-stream")
async def log_stream(session: str):
    q = session_queues.get(session)
    if q is None:
        raise HTTPException(404, "未知会话")

    async def generate():
        while True:
            try:
                msg = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: q.get(timeout=0.2)
                )
                data = json.loads(msg)
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                if data.get("level") == "DONE":
                    break
            except queue.Empty:
                # 发送心跳保持连接
                yield ": heartbeat\n\n"

        # 清理
        session_queues.pop(session, None)

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/api/download/{session_id}")
async def download(session_id: str):
    """下载产物 ZIP"""
    # 找到对应临时目录
    import glob
    matches = glob.glob(str(Path(tempfile.gettempdir()) / f"ard_web_{session_id}_*"))
    if not matches:
        raise HTTPException(404, "产物已过期或被清理")
    
    output_dir = Path(matches[0]) / 'output'
    zip_path = output_dir.parent / f"产物_{session_id}.zip"
    if not zip_path.exists():
        raise HTTPException(404, "产物尚未生成")
    
    return FileResponse(
        zip_path,
        filename=f"产物_{datetime.now():%Y%m%d_%H%M%S}.zip",
        media_type="application/zip"
    )

# ── 执行分发 ──────────────────────────────────────────

def _execute_mode(mode: str, file_path: Path, output_dir: Path,
                  custom_t_dir: Path, api_key: str, model: str, base_url: str):
    """根据 mode 调用现有核心函数（仅支持 from-excel-* 模式）"""
    from ai_gen_reimbursement_docs.config_utils import (
        load_api_key, load_base_url, load_model_name
    )

    api_key = api_key or load_api_key()
    model = model or load_model_name()
    base_url = base_url or load_base_url()

    if api_key:
        os.environ['ANTHROPIC_API_KEY'] = api_key
    if base_url:
        os.environ['ANTHROPIC_BASE_URL'] = base_url

    logger = logging.getLogger('ai_gen_reimbursement_docs')
    logger.info(f"模式: {mode}, 文件: {file_path.name}")

    _execute_excel_mode(mode, str(file_path), str(output_dir),
                       api_key, model, base_url, str(custom_t_dir))


def _execute_excel_mode(mode: str, xlsx_path: str, output_dir: str,
                        api_key: str, model: str, base_url: str,
                        custom_t_dir: str):
    """处理 from-excel 相关模式，调用链完全对照 main.py 中的实际实现。"""
    import os, re, shutil

    # ── 路径定义 ──
    doc_dir = os.path.join(output_dir, 'cosmic文档')
    os.makedirs(doc_dir, exist_ok=True)
    md_dir = os.path.join(output_dir, 'md')
    os.makedirs(md_dir, exist_ok=True)

    tree_md       = os.path.join(md_dir, 'gen-basedata-功能清单-模块树.md')
    meta_md_tpl   = os.path.join(md_dir, 'gen-basedata-录入文档元数据-模板.md')
    meta_filled_md = os.path.join(md_dir, 'gen-basedata-AI填充-录入文档元数据.md')
    fpa_sum_md    = os.path.join(md_dir, 'gen-fpa-FPA工作量-总和.md')

    fpa_xlsx       = os.path.join(output_dir, 'FPA工作量评估.xlsx')
    cosmic_xlsx    = os.path.join(doc_dir, '项目功能点拆分表.xlsx')
    require_xlsx   = os.path.join(doc_dir, '项目需求清单.xlsx')
    spec_docx      = os.path.join(doc_dir, '项目需求说明书.docx')

    # ── imports ──
    from ai_gen_reimbursement_docs.excel_source import generate_md_files, verify_module_tree_stats
    from ai_gen_reimbursement_docs.main import (
        _build_modules_from_tree_md, _ensure_basedata, _ai_fill_meta_md,
        _write_cfp_sum, _read_md_value, _resolve_fpa_sum, _project_root,
    )
    from ai_gen_reimbursement_docs.gen_xlsx import (
        generate_fpa_xlsx_from_md, generate_list_xlsx_from_md,
        init_fpa_template_md, ai_fill_fpa_md,
    )
    from ai_gen_reimbursement_docs.gen_spec import (
        generate_spec_docx_from_md, init_spec_template_md, ai_fill_spec_md,
        _parse_meta_md,
    )
    from ai_gen_reimbursement_docs.md_handler import (
        export_empty_md, fill_md_with_ai, parse_md_to_items,
    )
    from ai_gen_reimbursement_docs.excel_writer import (
        generate_cosmic_xlsx_from_md, write_environment_sheet,
    )
    from ai_gen_reimbursement_docs.cosmic_llm import load_user_config_from_meta
    from ai_gen_reimbursement_docs.config_utils import load_enable_ai_fill_meta

    logger = logging.getLogger('ai_gen_reimbursement_docs')

    # ── 公共辅助：确保基础数据 + 元数据 AI 填充 ──
    def ensure_meta():
        """确保树和元数据存在，必要时 AI 填充元数据。"""
        _ensure_basedata(xlsx_path, md_dir, meta_md, tree_md, meta_md_tpl)
        if api_key and not os.path.exists(meta_filled_md):
            if load_enable_ai_fill_meta():
                logger.info("AI 填充文档元数据...")
                _ai_fill_meta_md(meta_md_tpl, meta_filled_md, api_key, model, base_url, tree_md=tree_md)
            else:
                logger.info("enable_ai_fill_meta=false，跳过 AI 填充，直接复制模板")
                shutil.copy2(meta_md_tpl, meta_filled_md)
        return meta_filled_md if os.path.exists(meta_filled_md) else meta_md_tpl

    # 当前使用的 meta_md（优先填充版）
    meta_md = meta_filled_md if os.path.exists(meta_filled_md) else meta_md_tpl

    # ═══════════════════════════════════════════════════════
    #   gen-basedata
    # ═══════════════════════════════════════════════════════
    if mode == "from-excel-gen-basedata":
        logger.info("第1步: 生成 功能清单-模块树.md 和 录入文档元数据-模板.md...")
        generate_md_files(xlsx_path, md_dir)
        verify_module_tree_stats(tree_md, meta_md_tpl)
        if api_key and not os.path.exists(meta_filled_md):
            if load_enable_ai_fill_meta():
                logger.info("AI 填充文档元数据...")
                _ai_fill_meta_md(meta_md_tpl, meta_filled_md, api_key, model, base_url, tree_md=tree_md)
            else:
                shutil.copy2(meta_md_tpl, meta_filled_md)
        return

    # ═══════════════════════════════════════════════════════
    #   gen-fpa
    # ═══════════════════════════════════════════════════════
    if mode == "from-excel-gen-fpa":
        meta_md = ensure_meta()
        fpa_md = os.path.join(md_dir, 'gen-fpa-FPA-模板.md')
        fpa_filled_md = os.path.join(md_dir, 'gen-fpa-AI填充-FPA.md')
        logger.info("第1步: 生成 FPA 模板 MD...")
        init_fpa_template_md(tree_md, meta_md, fpa_md, summary_md_path=fpa_sum_md)
        if api_key:
            logger.info("第2步: AI 填充 FPA 数据...")
            shutil.copy2(fpa_md, fpa_filled_md)
            ai_fill_fpa_md(fpa_filled_md, meta_md, api_key=api_key, model=model, base_url=base_url)
        else:
            fpa_filled_md = fpa_md
        logger.info("第3步: 生成 FPA 工作量评估 Excel...")
        fpa_src_template = _get_template_path('FPA工作量评估-模板', custom_t_dir)
        generate_fpa_xlsx_from_md(fpa_filled_md, meta_md, fpa_src_template, fpa_xlsx)
        return

    # ═══════════════════════════════════════════════════════
    #   gen-cosmic
    # ═══════════════════════════════════════════════════════
    if mode == "from-excel-gen-cosmic":
        ensure_meta()
        meta_md = meta_filled_md if os.path.exists(meta_filled_md) else meta_md_tpl
        _resolve_fpa_sum(fpa_sum_md)  # 提示用户输入核减后工作量
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
                cosmic_src = _get_template_path('项目功能点拆分表-模板', custom_t_dir)
                generate_cosmic_xlsx_from_md(cosmic_src, cosmic_xlsx, items, meta=_meta)
                total_cfp = sum(item.total_cfp() for item in items)
                logger.info(f"CFP 总和: {total_cfp}")
                _write_cfp_sum(md_dir, total_cfp)
                _target = _meta.get("建设目标", "")
                _necessity = _meta.get("建设必要性", "")
                if _target or _necessity:
                    write_environment_sheet(cosmic_xlsx, cosmic_xlsx, project, _target, _necessity)
        return

    # ═══════════════════════════════════════════════════════
    #   gen-list
    # ═══════════════════════════════════════════════════════
    if mode == "from-excel-gen-list":
        ensure_meta()
        meta_md = meta_filled_md if os.path.exists(meta_filled_md) else meta_md_tpl
        # 尝试从已有文件中读取 CFP 和工作量
        cfp_val = _read_md_value(os.path.join(md_dir, 'gen-cosmic-CFP-总和.md'), r'CFP 总和[：:]\s*([\d.]+)') or 0
        fpa_val = _read_md_value(fpa_sum_md, r'FPA工作量（人/天）[：:]\s*([\d.]+)') or 0
        require_src = _get_template_path('项目需求清单-模板', custom_t_dir)
        generate_list_xlsx_from_md(meta_md, tree_md, require_src, require_xlsx,
                                   cfp_total=cfp_val, fpa_reduced=fpa_val)
        return

    # ═══════════════════════════════════════════════════════
    #   gen-spec
    # ═══════════════════════════════════════════════════════
    if mode == "from-excel-gen-spec":
        meta_md = ensure_meta()
        spec_md = os.path.join(md_dir, 'gen-spec-spec-功能需求章节-模板.md')
        spec_filled_md = os.path.join(md_dir, 'gen-spec-AI填充-spec-功能需求章节.md')
        if not os.path.exists(spec_filled_md):
            logger.info("生成 spec 模板 MD...")
            init_spec_template_md(tree_md, meta_md, spec_md)
            if api_key:
                logger.info("AI 填充模块功能描述...")
                ai_fill_spec_md(spec_md, spec_filled_md, api_key, model, base_url)
            else:
                shutil.copy2(spec_md, spec_filled_md)
        filled = spec_filled_md if os.path.exists(spec_filled_md) else ""
        spec_src = _get_template_path('项目需求说明书-模板', custom_t_dir)
        generate_spec_docx_from_md(spec_src, spec_docx, meta_md, tree_md, filled_md_path=filled)
        return

    # ═══════════════════════════════════════════════════════
    #   gen-all（全流程，按依赖顺序）
    # ═══════════════════════════════════════════════════════
    if mode == "from-excel-gen-all":
        # Step 0: 基础数据
        _ensure_basedata(xlsx_path, md_dir, meta_md, tree_md, meta_md_tpl)
        if api_key and not os.path.exists(meta_filled_md):
            if load_enable_ai_fill_meta():
                _ai_fill_meta_md(meta_md_tpl, meta_filled_md, api_key, model, base_url, tree_md=tree_md)
            else:
                shutil.copy2(meta_md_tpl, meta_filled_md)
        if os.path.exists(meta_filled_md):
            meta_md = meta_filled_md

        fpa_src = _get_template_path('FPA工作量评估-模板', custom_t_dir)
        cosmic_src = _get_template_path('项目功能点拆分表-模板', custom_t_dir)
        require_src = _get_template_path('项目需求清单-模板', custom_t_dir)
        spec_src = _get_template_path('项目需求说明书-模板', custom_t_dir)

        # Step 1: FPA
        fpa_md = os.path.join(md_dir, 'gen-fpa-FPA-模板.md')
        fpa_filled_md = os.path.join(md_dir, 'gen-fpa-AI填充-FPA.md')
        logger.info("第1步：生成 FPA 模板 MD...")
        init_fpa_template_md(tree_md, meta_md, fpa_md, summary_md_path=fpa_sum_md)
        if api_key:
            shutil.copy2(fpa_md, fpa_filled_md)
            logger.info("第1步：AI 填充 FPA...")
            ai_fill_fpa_md(fpa_filled_md, meta_md, template_path=fpa_src, api_key=api_key, model=model, base_url=base_url)
        fpa_src_md = fpa_filled_md if api_key else fpa_md
        generate_fpa_xlsx_from_md(fpa_src_md, meta_md, fpa_src, fpa_xlsx)

        fpa_reduced = _read_md_value(fpa_sum_md, r'FPA工作量（人/天）[：:]\s*([\d.]+)') or 0.0

        # Step 2: 需求说明书
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

        # Step 3: COSMIC
        modules = _build_modules_from_tree_md(tree_md)
        project = modules[0].name if modules else "项目"
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
                total_cfp = sum(item.total_cfp() for item in items)
                _write_cfp_sum(md_dir, total_cfp)
                _target = _meta.get("建设目标", "")
                _necessity = _meta.get("建设必要性", "")
                if _target or _necessity:
                    write_environment_sheet(cosmic_xlsx, cosmic_xlsx, project, _target, _necessity)

        cfp_total = _read_md_value(os.path.join(md_dir, 'gen-cosmic-CFP-总和.md'), r'CFP 总和[：:]\s*([\d.]+)') or 0

        # Step 4: 需求清单
        generate_list_xlsx_from_md(meta_md, tree_md, require_src, require_xlsx,
                                   cfp_total=cfp_total, fpa_reduced=fpa_reduced)
        return


# ── 模板路径解析 ────────────────────────────────────────

def _get_template_path(key: str, custom_t_dir: str) -> str:
    """获取模板路径：优先自定义模板目录，回退 data/templates/"""
    import glob as _glob
    patterns = {
        'FPA工作量评估-模板':     'FPA*评估*模板*.xlsx',
        '项目功能点拆分表-模板':   '*功能点拆分表*模板*.xlsx',
        '项目需求清单-模板':       '*需求清单*模板*.xlsx',
        '项目需求说明书-模板':     '*需求说明书*模板*.docx',
    }
    pat = patterns.get(key, '')
    if pat and custom_t_dir:
        matches = _glob.glob(os.path.join(custom_t_dir, pat))
        if matches:
            return matches[0]
    return os.path.join(str(BASE_DIR / 'data' / 'templates'), key + '.xlsx' if key != '项目需求说明书-模板' else key + '.docx')


def _read_project_name(meta_md: str) -> str:
    """从元数据 MD 读取项目名称"""
    if not os.path.exists(meta_md):
        return ""
    with open(meta_md, encoding='utf-8') as f:
        for line in f:
            m = re.search(r'工单标题\s*\|\s*(.+?)(?:\s*\||$)', line)
            if m:
                return m.group(1).strip()
    return ""

---

## 8. index.html 完整结构

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 报账文档生成器</title>
    <style>
        /* 约 150 行 CSS：布局、颜色、日志面板样式 */
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, sans-serif; background: #f0f2f5; color: #333; }
        .app { display: flex; height: 100vh; }
        .panel-left { width: 360px; padding: 20px; background: #fff; border-right: 1px solid #e0e0e0; }
        .panel-right { flex: 1; display: flex; flex-direction: column; }
        .log-panel { flex: 1; padding: 20px; overflow-y: auto; background: #1e1e1e; color: #d4d4d4; font-family: monospace; }
        .download-panel { padding: 16px 20px; background: #fff; border-top: 1px solid #e0e0e0; }
        /* ... 更多样式 */
    </style>
</head>
<body>
    <div class="app">
        <!-- 左侧配置区 -->
        <div class="panel-left">
            <h2>AI 报账文档生成器</h2>
            <div class="form-group">
                <label>操作模式</label>
                <select id="mode"></select>
            </div>
            <div class="form-group">
                <label>上传文件</label>
                <input type="file" id="file" />
            </div>
            <details>
                <summary>高级选项</summary>
                <div class="form-group">
                    <label>API Key</label>
                    <input type="password" id="api_key" placeholder="留空使用系统配置" />
                </div>
                <div class="form-group">
                    <label>模型</label>
                    <input type="text" id="model" placeholder="deepseek-v4-flash" />
                </div>
                <div class="form-group">
                    <label>API 端点</label>
                    <input type="text" id="base_url" placeholder="留空使用默认" />
                </div>
            </details>
            <button id="btn-run" onclick="startTask()">▶ 开始生成</button>
            <div id="status" class="status-idle">● 就绪</div>
        </div>

        <!-- 右侧日志+下载区 -->
        <div class="panel-right">
            <div class="log-panel" id="log-panel">
                <div class="log-placeholder">等待任务开始...</div>
            </div>
            <div class="download-panel">
                <button id="btn-download" disabled onclick="download()">⬇ 下载产物</button>
            </div>
        </div>
    </div>

    <script>
        // 约 150 行 JS
        const MODES = {/* 从后端 /api/modes 获取或硬编码 */};
        let currentSession = null;
        let eventSource = null;

        function init() {
            // 初始化模式下拉框
            // 根据模式切换接受的文件类型
        }

        async function startTask() {
            // 1. 禁用按钮
            // 2. 构建 FormData
            // 3. POST /api/run
            // 4. 获取 session_id
            // 5. 连接 SSE /api/log-stream?session=xxx
        }

        function appendLog(level, msg, time) {
            // 追加日志行到 log-panel
        }

        function onTaskDone() {
            // 启用下载按钮
            // 自动触发下载
        }

        function download() {
            // GET /api/download/{session_id}
        }

        init();
    </script>
</body>
</html>
```

---

## 9. 启动方式

```bash
# 1. 安装 Web 依赖
pip install fastapi uvicorn python-multipart

# 2. 启动服务
cd f:/mlt/mlt-projects/ai_cosmic
python -m uvicorn web_app.server:app --host 0.0.0.0 --port 8080

# 3. 浏览器打开
# http://localhost:8080

# 4. 局域网内其他设备访问
# http://<本机IP>:8080
```

### 生产部署（可选）

```bash
# 多 worker 模式（每个 worker 独立进程，注意日志队列需改用 Redis）
uvicorn web_app.server:app --host 0.0.0.0 --port 8080 --workers 4

# 或用 gunicorn（Linux）
gunicorn web_app.server:app -w 4 -k uvicorn.workers.UvicornWorker
```

> **注意**：`--workers 4` 多 worker 模式下，内存中的 `session_queues` 字典不共享，SSE 连接和 API 请求必须在同一 worker。对于 3-5 人场景，单 worker 足够；如需多 worker，将 session_queues 改为 Redis Pub/Sub。

---

## 10. 限制与后续扩展

### 10.1 当前方案的限制

| 限制 | 说明 | 影响 |
|------|------|------|
| 无用户认证 | 任何人可访问 | 部署在内网使用 |
| 内存存储 | session 队列在内存中 | 服务重启后正在跑的任务丢失 |
| 单 worker | 多 worker 时 SSE 跨进程不可达 | 限制并发上限 |
| 无持久化 | 产物临时目录定时清理 | 历史记录不保存 |
| 同步执行 | AI 调用阻塞线程 | 单个请求可能占一个线程 60s |

### 10.2 后续可扩展方向

- **用户认证**：加 HTTP Basic Auth 或 JWT
- **任务队列**：Celery + Redis 替代线程池，支持真正的异步和重试
- **持久化**：SQLite 存历史任务记录
- **产物管理**：下载链接保持 24 小时有效
- **Docker 部署**：提供 Dockerfile 一键部署

---

## 11. 实施检查清单

- [ ] 新建 `web_app/` 目录
- [ ] 新建 `web_app/server.py`，实现三个 API 端点
- [ ] 新建 `web_app/static/index.html`，实现前端页面
- [ ] `pyproject.toml` 添加 fastapi / uvicorn / python-multipart 依赖
- [ ] 补全 `_execute_excel_mode` 中各模式的具体调用链
- [ ] 测试：上传 xlsx → 全套 → 下载 zip
- [ ] 测试：上传 xlsx → 单个模式（fpa/cosmic/list/spec）→ 下载产物
- [ ] 测试：两个浏览器同时访问，日志不串
- [ ] 测试：CLI 和 Web 同时使用，互不影响
