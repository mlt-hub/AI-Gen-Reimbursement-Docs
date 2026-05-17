# Web UI 套壳方案

## 1. 概述

为现有 CLI 工具 `ai-gen-reimbursement-docs` 添加 Web 界面，实时查看日志，下载生成产物。支持两种使用方式。

### 两种模式

| 模式 | 适用场景 | 文件输入 | 产物输出 |
|---|---|---|---|
| **本机模式** | 单人在本机使用 | 直接读本地路径 | 写到本地目录，点按钮打开 |
| **服务模式** | 多人远程访问 | 浏览器上传文件 | 下载 ZIP |

同一套 server + 同一套前端，前端切换模式。

### 核心原则

- **零侵入**：不修改 `ai_gen_reimbursement_docs/` 下任何文件
- **可并存**：Web 和 CLI 各自独立进程，同时使用互不影响

### 技术栈

| 层 | 选择 | 原因 |
|---|---|---|
| Web 框架 | FastAPI | 异步、原生 SSE |
| 前端 | 单 HTML + vanilla JS + CSS | 无构建工具、无 npm、开箱即用 |
| 并发 | `asyncio.to_thread` + 线程池 | 同步 AI 调用放线程池，不阻塞事件循环 |
| 日志隔离 | `contextvars` + 自定义 Handler | 日志按会话路由到不同 SSE 连接 |

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
│  ┌─ 本机模式 ──────────────────────────────────────────────┐               
│  │ POST /api/run-local                                      │              
│  │ (xlsx路径+输出目录+参数)                                    │              
│  │ ───────────────────────→  直接读本地 xlsx                   │              
│  │                           asyncio.to_thread(run_pipeline)  │              
│  │                           产物写本地目录                     │              
│  │ ←─ {session_id} ───────                                   │              
│  │ GET /api/open-folder?session=xxx                           │              
│  │ ───────────────────────→  os.startfile(output_dir)         │              
│  └──────────────────────────────────────────────────────────┘              
│                                                                           
│  ┌─ 服务模式 ──────────────────────────────────────────────┐               
│  │ POST /api/run-upload                                     │              
│  │ (上传文件+参数)                                            │              
│  │ ───────────────────────→  保存到 /tmp/ard_web_{session}/             
│  │                           asyncio.to_thread(run_pipeline)  │              
│  │                           打包产物 ZIP                     │              
│  │ ←─ {session_id} ───────                                   │              
│  │ GET /api/download/{session_id}                             │              
│  │ ←─ ZIP 下载 ──────────                                     │              
│  └──────────────────────────────────────────────────────────┘              
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

### 4.2 共用参数

**操作模式**（仅支持 from-excel 流程）：

| mode 值 | 对应 CLI |
|---------|----------|
| `from-excel-gen-all` | `--from-excel x.xlsx --gen-all` |
| `from-excel-gen-basedata` | `--from-excel x.xlsx --gen-basedata` |
| `from-excel-gen-fpa` | `--from-excel x.xlsx --gen-fpa` |
| `from-excel-gen-cosmic` | `--from-excel x.xlsx --gen-cosmic` |
| `from-excel-gen-list` | `--from-excel x.xlsx --gen-list` |
| `from-excel-gen-spec` | `--from-excel x.xlsx --gen-spec` |

**可选参数**（两种模式共用）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `api_key` | string | API Key，不填用系统配置 |
| `model` | string | 模型名，默认 `deepseek-v4-flash` |
| `base_url` | string | API 端点，默认用系统配置 |

### 4.3 POST `/api/run-local`（本机模式）

直接操作本地文件，无上传无下载。

**请求**（JSON）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `xlsx_path` | string | 是 | 本地 .xlsx 路径 |
| `output_dir` | string | 否 | 输出目录，默认 xlsx 同级 |
| `mode` | string | 是 | 操作模式 |
| `api_key` | string | 否 | 同上 |
| `model` | string | 否 | 同上 |
| `base_url` | string | 否 | 同上 |

**响应**：

- 成功：`{"session_id": "xxx", "output_dir": "/path/to/output"}`
- 失败：`{"error": "..."}`

### 4.4 POST `/api/run-upload`（服务模式）

上传文件，完成后下载 ZIP。

**请求**（multipart/form-data）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | file | 是 | .xlsx 功能清单文件 |
| `mode` | string | 是 | 操作模式 |
| `api_key` | string | 否 | 同上 |
| `model` | string | 否 | 同上 |
| `base_url` | string | 否 | 同上 |
| `fpa_template` | file | 否 | 自定义模板 |
| `cosmic_template` | file | 否 | 同上 |
| `list_template` | file | 否 | 同上 |
| `spec_template` | file | 否 | 同上 |

**响应**：

- 成功：`{"session_id": "xxx", "has_download": true}`
- 失败：`{"error": "..."}`

### 4.5 GET `/api/log-stream?session=xxx`

SSE 端点，推送指定 session 的实时日志。

**事件格式**：

```
data: {"level": "INFO", "msg": "正在AI填充 12 个模块...", "time": "14:30:01"}

data: {"level": "DEBUG", "msg": "API调用完成", "time": "14:30:15"}

data: {"level": "DONE"}
```

前端连接此端点后持续接收日志，收到 `DONE` 后断开。

### 4.6 GET `/api/download/{session_id}`（服务模式）

下载产物 ZIP，下载完成后 5 分钟自动清理临时目录。

### 4.7 GET `/api/open-folder?session=xxx`（本机模式）

调用 `os.startfile(output_dir)` 在资源管理器中打开产物目录。

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

### 5.4 临时文件清理（仅服务模式）

服务模式下每个请求在 `/tmp/ard_web_{session}/` 下创建独立工作目录。本机模式产物直接写用户指定目录，无需清理。

```
┌─ 请求到达 → 创建 /tmp/ard_web_{abc123}/
│
├─ 管道执行 → 产物写入 output/
├─ 打包 ZIP  → /tmp/ard_web_{abc123}/产物_abc123.zip
│
├─ 用户下载 → 返回 ZIP
│
└─ 下载后 5 分钟 → 删除整个 /tmp/ard_web_{abc123}/
     ├─ session_dirs.pop(session_id)
     ├─ session_queues.pop(session_id)
     ├─ session_zips.pop(session_id)
     └─ shutil.rmtree(work_dir)
```

- 未下载的会话：服务重启时 `/tmp` 由系统清理
- 边缘情况：下载失败/用户离开 → 临时目录残留，重启后自动回收

---

## 6. 前端页面

### 6.1 布局

```
┌──────────────────────────────────────────────────────┐
│  🤖 AI 报账文档生成器                    v5.0.0       │
├──────────────────────┬───────────────────────────────┤
│  📋 配置              │  📄 实时日志                   │
│                      │                               │
│  使用方式 ●本机 ○远程  │  ┌──────────────────────────┐ │
│                      │  │ 14:30:01  解析模块...     │ │
│  操作模式             │  │ 14:30:05  AI 填充中...    │ │
│  [下拉选择        ▾] │  │ 14:30:20  生成 Excel ✓   │ │
│                      │  │ 14:30:21  打包完成        │ │
│  ── 本机：文件路径 ── │  │ 14:30:22  ── 完成 ──     │ │
│  xlsx 路径            │  │                           │ │
│  [C:\...\功能清单.xlsx]│  └──────────────────────────┘ │
│  输出目录（默认同级）    │                               │
│  [C:\...\output     ] │  状态: ● 运行中               │
│                      │                               │
│  [浏览...] [▶ 开始]   │  📂 [打开产物目录]            │
│                      │                               │
│  ── 远程：上传文件 ── │  ┌─ 切换远程模式后显示 ────┐ │
│  [选择文件         ] │  │ 📦 [⬇ 下载产物.zip]    │ │
│  已选: 功能清单.xlsx  │  └──────────────────────────┘ │
│                      │                               │
│  ── 高级选项 ─────── │                               │
│  API Key              │                               │
│  [··············  ]  │                               │
│  模型                 │                               │
│  [[deepseek-v4-flash]]│                               │
│  自定义端点            │                               │
│  [留空用默认        ] │                               │
└──────────────────────┴───────────────────────────────┘
```

### 6.2 交互逻辑

```
本机模式：
1. 用户选择模式「本机」、操作模式、填写 xlsx 路径和输出目录
2. 点击 [开始生成]
3. 前端 POST /api/run-local → 拿到 session_id
4. 前端 GET /api/log-stream → SSE 实时日志
5. 收到 DONE → [打开产物目录] 按钮激活
6. 点击按钮 → GET /api/open-folder → 资源管理器打开目录

服务模式：
1. 用户选择模式「远程」、操作模式、选择上传文件
2. 点击 [开始生成]
3. 前端 POST /api/run-upload → 拿到 session_id
4. 前端 GET /api/log-stream → SSE 实时日志
5. 收到 DONE → [下载产物.zip] 按钮激活
6. 下载完成后 5 分钟服务端自动清理
```

### 6.3 技术细节

- 纯 HTML + CSS + vanilla JS，无框架
- 模式切换时动态显示/隐藏对应区域（`display:none` / `display:block`）
- 本机模式发 JSON（`Content-Type: application/json`），服务模式发 FormData
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
session_outputs: dict[str, Path] = {}     # session_id → 产物目录（两种模式共用）
session_zips: dict[str, Path] = {}        # session_id → zip 文件路径（服务模式）
session_dirs: dict[str, Path] = {}        # session_id → 临时工作目录（服务模式）

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

@app.post("/api/run-local")
async def api_run_local(
    xlsx_path: str = Form(...),
    output_dir: str = Form(""),
    mode: str = Form(...),
    api_key: str = Form(""),
    model: str = Form(""),
    base_url: str = Form(""),
):
    """本机模式：直接读本地文件，产物写本地目录。"""
    if mode not in MODE_INFO:
        raise HTTPException(400, f"未知模式: {mode}")

    xlsx = Path(xlsx_path)
    if not xlsx.exists():
        raise HTTPException(400, f"文件不存在: {xlsx_path}")

    out = Path(output_dir) if output_dir else xlsx.parent
    out.mkdir(parents=True, exist_ok=True)

    session_id = uuid.uuid4().hex[:8]
    log_queue: queue.Queue = queue.Queue(maxsize=500)
    session_queues[session_id] = log_queue
    session_outputs[session_id] = out

    def run():
        session_var.set(session_id)
        try:
            _execute_mode(mode, xlsx, out, Path(""), api_key, model, base_url)
        except Exception as e:
            logging.getLogger('ai_gen_reimbursement_docs').error(f"执行失败: {e}")
        finally:
            log_queue.put(json.dumps({"level": "DONE"}, ensure_ascii=False))
            session_var.set(None)

    asyncio.create_task(asyncio.to_thread(run))
    return {"session_id": session_id, "output_dir": str(out)}


@app.post("/api/run-upload")
async def api_run_upload(
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
    session_dirs[session_id] = work_dir

    # 6. 在线程池中执行
    def run():
        session_var.set(session_id)
        try:
            _execute_mode(mode, file_path, output_dir, custom_t_dir,
                         api_key, model, base_url)
            # 打包产物为 ZIP
            zip_path = work_dir / f"产物_{session_id}.zip"
            shutil.make_archive(str(zip_path.with_suffix('')), 'zip', str(output_dir))
            session_zips[session_id] = zip_path
        except Exception as e:
            logging.getLogger('ai_gen_reimbursement_docs').error(f"执行失败: {e}")
        finally:
            log_queue.put(json.dumps({"level": "DONE"}, ensure_ascii=False))
            session_var.set(None)

    asyncio.create_task(asyncio.to_thread(run))

    return {"session_id": session_id, "has_download": True}

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

        # 清理队列引用（目录和 zip 由 _cleanup_after_download 负责）
        session_queues.pop(session, None)

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/api/download/{session_id}")
async def download(session_id: str):
    """下载产物 ZIP"""
    zip_path = session_zips.get(session_id)
    if zip_path is None:
        raise HTTPException(404, "产物不存在或会话已过期")
    if not zip_path.exists():
        raise HTTPException(404, "产物文件已被清理")

    return FileResponse(
        zip_path,
        filename=f"产物_{datetime.now():%Y%m%d_%H%M%S}.zip",
        media_type="application/zip",
        background=_cleanup_after_download(session_id),
    )

@app.get("/api/open-folder")
async def open_folder(session: str):
    """本机模式：在资源管理器中打开产物目录。"""
    out_dir = session_outputs.get(session)
    if out_dir is None:
        raise HTTPException(404, "未知会话")
    if not out_dir.exists():
        raise HTTPException(404, "产物目录不存在")
    os.startfile(str(out_dir))
    return {"ok": True}

# ── 清理 ──────────────────────────────────────────────

async def _cleanup_after_download(session_id: str):
    """下载完成后延迟 5 分钟清理临时目录，避免清理正在被扫描的产物。"""
    await asyncio.sleep(300)
    work_dir = session_dirs.pop(session_id, None)
    session_queues.pop(session_id, None)
    session_zips.pop(session_id, None)
    if work_dir and work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)

# ── 执行分发 ──────────────────────────────────────────

# mode → pipeline mode 映射
_MODE_MAP: dict[str, str] = {
    "from-excel-gen-all":      "gen-all",
    "from-excel-gen-basedata": "gen-basedata",
    "from-excel-gen-fpa":      "gen-fpa",
    "from-excel-gen-cosmic":   "gen-cosmic",
    "from-excel-gen-list":     "gen-list",
    "from-excel-gen-spec":     "gen-spec",
}


def _execute_mode(mode: str, file_path: Path, output_dir: Path,
                  custom_t_dir: Path, api_key: str, model: str,
                  base_url: str, project_name: str = ""):
    """直接调用 pipeline.run_pipeline()，零重复代码。"""
    from ai_gen_reimbursement_docs.pipeline import run_pipeline
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

    pipeline_mode = _MODE_MAP[mode]

    # 构建 templates dict（自定义模板优先）
    templates = _build_templates_dict(custom_t_dir)

    run_pipeline(
        mode=pipeline_mode,
        file_path=str(file_path),
        output_dir=str(output_dir),
        api_key=api_key,
        model=model,
        base_url=base_url,
        project_name=project_name,
        templates=templates or None,
    )


def _build_templates_dict(custom_t_dir: Path) -> dict[str, str]:
    """构建 templates dict：自定义模板目录中的文件优先。"""
    import glob as _glob
    templates: dict[str, str] = {}
    custom = str(custom_t_dir)
    for key, glob_pat in [
        ('fpa',    'FPA*评估*模板*.xlsx'),
        ('cosmic', '*功能点拆分表*模板*.xlsx'),
        ('list',   '*需求清单*模板*.xlsx'),
        ('spec',   '*需求说明书*模板*.docx'),
    ]:
        matches = _glob.glob(os.path.join(custom, glob_pat))
        if matches:
            templates[key] = matches[0]
    return templates


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
