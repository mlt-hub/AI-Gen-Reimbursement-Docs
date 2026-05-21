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
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# ── 日志隔离 ──────────────────────────────────────────────

session_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "session_id", default=None
)
session_queues: dict[str, queue.Queue] = {}
session_outputs: dict[str, Path] = {}  # session_id → 产物目录（本机模式）
session_zips: dict[str, Path] = {}  # session_id → zip 文件路径（服务模式）
session_dirs: dict[str, Path] = {}  # session_id → 临时工作目录（服务模式）


class SessionHandler(logging.Handler):
    """将日志路由到对应 session 的队列，实现多会话日志隔离。"""

    def emit(self, record):
        sid = session_var.get()
        if sid and sid in session_queues:
            msg = json.dumps(
                {
                    "level": record.levelname,
                    "msg": self.format(record),
                    "time": datetime.fromtimestamp(record.created).strftime(
                        "%H:%M:%S"
                    ),
                },
                ensure_ascii=False,
            )
            try:
                session_queues[sid].put_nowait(msg)
            except queue.Full:
                pass  # 队列满时丢弃旧日志，优先保留关键信息


# 确保父 logger 级别足够低，子 logger 的 INFO/DEBUG 能传播过来
_parent = logging.getLogger("ai_gen_reimbursement_docs")
_parent.setLevel(logging.DEBUG)

_handler = SessionHandler()
_handler.setLevel(logging.DEBUG)
_handler.setFormatter(logging.Formatter("%(message)s"))
_parent.addHandler(_handler)

# 添加全局日志 handler（与 CLI 一致）
from ai_gen_reimbursement_docs.cli.logging import init_global_logging
init_global_logging()

# ── 常量 ──────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "data" / "out_templates"

_log = logging.getLogger("ai_gen_reimbursement_docs")
_log.info("[Web UI] AI生成项目报账文档 v%s（FastAPI 服务启动）",
          __import__('tomllib').load(open(BASE_DIR / 'pyproject.toml', 'rb'))['project']['version'])

MODE_INFO: dict[str, dict[str, str]] = {
    "from-excel-gen-all": {"label": "全流程 → 全套交付物", "desc": "生成所有文档"},
    "from-excel-gen-basedata": {
        "label": "基础数据 → 模块树+元数据",
        "desc": "仅解析 Excel 生成中间 MD",
    },
    "from-excel-gen-fpa": {"label": "FPA → 工作量评估", "desc": "生成 FPA工作量评估.xlsx"},
    "from-excel-gen-cosmic": {
        "label": "COSMIC → 功能点拆分表",
        "desc": "生成 项目功能点拆分表.xlsx",
    },
    "from-excel-gen-list": {"label": "需求清单", "desc": "生成 项目需求清单.xlsx"},
    "from-excel-gen-spec": {"label": "需求说明书", "desc": "生成 项目需求说明书.docx"},
}

_MODE_MAP: dict[str, str] = {
    "from-excel-gen-all": "gen-all",
    "from-excel-gen-basedata": "gen-basedata",
    "from-excel-gen-fpa": "gen-fpa",
    "from-excel-gen-cosmic": "gen-cosmic",
    "from-excel-gen-list": "gen-list",
    "from-excel-gen-spec": "gen-spec",
}

# ── FastAPI App ───────────────────────────────────────────

app = FastAPI(title="AI 报账文档生成器")

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    content = html_path.read_text(encoding="utf-8")
    return HTMLResponse(content)


@app.get("/config")
async def config_page():
    html_path = Path(__file__).parent / "static" / "config.html"
    content = html_path.read_text(encoding="utf-8")
    return HTMLResponse(content)


@app.get("/prompt-debug")
async def prompt_debug():
    html_path = Path(__file__).parent / "static" / "prompt-debug.html"
    content = html_path.read_text(encoding="utf-8")
    return HTMLResponse(content)


@app.get("/api/modes")
async def get_modes():
    """返回操作模式列表，供前端动态渲染下拉框。"""
    return MODE_INFO


# ── 系统配置 ──────────────────────────────────────────────


def _config_dir() -> Path:
    return Path(os.path.expanduser("~")) / ".ai-gen-reimbursement-docs"


def _read_config() -> dict:
    """读取所有配置文件，返回合并后的 dict。"""
    cfg_dir = _config_dir()
    result: dict = {"_env": {}, "_system": {}, "_biz": {}}

    env_path = cfg_dir / ".env"
    if env_path.exists():
        env: dict[str, str] = {}
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
        result["_env"] = env

    for key, filename in [
        ("_system", "system_config.yaml"),
        ("_biz", "business_rules.yaml"),
    ]:
        path = cfg_dir / filename
        if path.exists():
            try:
                import yaml
                result[key] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                pass

    return result


@app.get("/api/config")
async def get_config():
    return _read_config()


@app.post("/api/config")
async def save_config(data: dict):
    """保存配置。data 含 _env / _system / _biz 三个 key。"""
    cfg_dir = _config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)

    if "_env" in data and data["_env"]:
        lines = []
        for k, v in data["_env"].items():
            lines.append(f"{k}={v}")
        (cfg_dir / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for key, filename in [("_system", "system_config.yaml"), ("_biz", "business_rules.yaml")]:
        if key in data and data[key]:
            import yaml
            path = cfg_dir / filename
            path.write_text(yaml.dump(data[key], allow_unicode=True, default_flow_style=False), encoding="utf-8")

    return {"ok": True}


# ── 提示词调试 ────────────────────────────────────────────


@app.post("/api/test-prompt")
async def test_prompt(data: dict):
    """提交系统提示词和用户提示词，返回 AI 生成结果。"""
    system_prompt = data.get("system_prompt", "").strip()
    user_prompt = data.get("user_prompt", "").strip()
    if not user_prompt and not system_prompt:
        raise HTTPException(400, "系统提示词和用户提示词不能同时为空")

    from ai_gen_reimbursement_docs.config_utils import (
        load_api_key, load_base_url, load_model_name,
    )
    from ai_gen_reimbursement_docs.llm_client import call_llm

    api_key = data.get("api_key", "").strip() or load_api_key()
    model = data.get("model", "").strip() or load_model_name()
    base_url = data.get("base_url", "").strip() or load_base_url()

    if not api_key:
        raise HTTPException(400, "未配置 API Key")

    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
    if base_url:
        os.environ["ANTHROPIC_BASE_URL"] = base_url

    try:
        result, thinking = call_llm(
            prompt=user_prompt,
            system=system_prompt,
            api_key=api_key,
            model=model,
            base_url=base_url,
            tag="prompt_debug",
            return_thinking=True,
        )
        return {
            "result": result,
            "thinking": thinking,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }
    except Exception as e:
        raise HTTPException(500, f"AI 调用失败: {e}")


# ── 本机模式 ──────────────────────────────────────────────


@app.post("/api/run-local")
async def api_run_local(
    xlsx_path: str = Form(...),
    output_dir: str = Form(""),
    mode: str = Form(...),
    api_key: str = Form(""),
    model: str = Form(""),
    base_url: str = Form(""),
    max_tokens: str = Form(""),
    project_name: str = Form(""),
    clean: str = Form(""),
    fpa_template: UploadFile | None = File(None),
    cosmic_template: UploadFile | None = File(None),
    list_template: UploadFile | None = File(None),
    spec_template: UploadFile | None = File(None),
):
    """本机模式：直接读本地文件，产物写本地目录。"""
    if mode not in MODE_INFO:
        raise HTTPException(400, f"未知模式: {mode}")

    xlsx = Path(xlsx_path)
    if not xlsx.exists():
        raise HTTPException(400, f"文件不存在: {xlsx_path}")

    if output_dir:
        out = Path(output_dir)
    else:
        out = xlsx.parent
    out.mkdir(parents=True, exist_ok=True)

    custom_t_dir = await _save_custom_templates(
        out, fpa_template, cosmic_template, list_template, spec_template
    )

    session_id = uuid.uuid4().hex[:8]
    log_queue: queue.Queue = queue.Queue(maxsize=2000)
    session_queues[session_id] = log_queue
    session_outputs[session_id] = out

    def run():
        session_var.set(session_id)
        try:
            _execute_mode(
                mode, str(xlsx), str(out), custom_t_dir,
                api_key, model, base_url, project_name,
                max_tokens=max_tokens, clean=bool(clean),
            )
        except Exception as e:
            logging.getLogger("ai_gen_reimbursement_docs").error(f"执行失败: {e}")
        finally:
            log_queue.put(json.dumps({"level": "DONE"}, ensure_ascii=False))
            session_var.set(None)

    asyncio.create_task(asyncio.to_thread(run))
    return {"session_id": session_id, "output_dir": str(out)}


# ── 服务模式 ──────────────────────────────────────────────


@app.post("/api/run-upload")
async def api_run_upload(
    file: UploadFile = File(...),
    mode: str = Form(...),
    api_key: str = Form(""),
    model: str = Form(""),
    base_url: str = Form(""),
    max_tokens: str = Form(""),
    project_name: str = Form(""),
    clean: str = Form(""),
    fpa_template: UploadFile | None = File(None),
    cosmic_template: UploadFile | None = File(None),
    list_template: UploadFile | None = File(None),
    spec_template: UploadFile | None = File(None),
):
    """服务模式：上传文件，产物打包 ZIP 下载。"""
    if mode not in MODE_INFO:
        raise HTTPException(400, f"未知模式: {mode}")

    if not file.filename:
        raise HTTPException(400, "未选择文件")

    session_id = uuid.uuid4().hex[:8]
    work_dir = Path(tempfile.mkdtemp(prefix=f"ard_web_{session_id}_"))
    input_dir = work_dir / "input"
    output_dir = work_dir / "output"
    custom_t_dir = work_dir / "custom_templates"
    for d in [input_dir, output_dir, custom_t_dir]:
        d.mkdir(parents=True)

    # 保存上传的 xlsx
    safe_name = Path(file.filename).name
    file_path = input_dir / safe_name
    content = await file.read()
    file_path.write_bytes(content)

    # 保存自定义模板
    await _save_custom_templates_into(
        custom_t_dir, fpa_template, cosmic_template, list_template, spec_template
    )

    log_queue: queue.Queue = queue.Queue(maxsize=2000)
    session_queues[session_id] = log_queue
    session_dirs[session_id] = work_dir

    def run():
        session_var.set(session_id)
        try:
            _execute_mode(
                mode, str(file_path), str(output_dir), str(custom_t_dir),
                api_key, model, base_url, project_name,
                max_tokens=max_tokens, clean=bool(clean),
            )
            # 打包产物 ZIP
            zip_path = work_dir / f"产物_{session_id}.zip"
            shutil.make_archive(
                str(zip_path.with_suffix("")), "zip", str(output_dir)
            )
            session_zips[session_id] = zip_path
        except Exception as e:
            logging.getLogger("ai_gen_reimbursement_docs").error(f"执行失败: {e}")
        finally:
            log_queue.put(json.dumps({"level": "DONE"}, ensure_ascii=False))
            session_var.set(None)

    asyncio.create_task(asyncio.to_thread(run))
    return {"session_id": session_id, "has_download": True}


# ── SSE 日志流 ────────────────────────────────────────────


@app.get("/api/log-stream")
async def log_stream(session: str):
    q = session_queues.get(session)
    if q is None:
        raise HTTPException(404, "未知会话")

    async def generate():
        while True:
            try:
                msg = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: q.get(timeout=0.1)
                )
                data = json.loads(msg)
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                if data.get("level") == "DONE":
                    break
            except queue.Empty:
                yield ": heartbeat\n\n"

        session_queues.pop(session, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── 产物操作 ──────────────────────────────────────────────


@app.get("/api/download/{session_id}")
async def download(session_id: str):
    """服务模式：下载产物 ZIP。"""
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


# ── AI 交互日志 ────────────────────────────────────────────


def _find_log_dir(session_id: str) -> Path | None:
    """根据 session 找到日志目录。"""
    out_dir = session_outputs.get(session_id)
    if out_dir is None:
        work_dir = session_dirs.get(session_id)
        if work_dir:
            out_dir = work_dir / "output"
    if out_dir is None or not out_dir.exists():
        return None

    # 搜索「日志」目录
    for log_dir in out_dir.rglob("日志"):
        if log_dir.is_dir():
            return log_dir
    return None


@app.get("/api/ai-log/{session_id}")
async def get_ai_log(session_id: str):
    """返回 AI 对话日志内容。"""
    log_dir = _find_log_dir(session_id)
    if log_dir is None:
        raise HTTPException(404, "未找到日志目录")

    combined = log_dir / "ai_对话日志.md"
    if not combined.exists():
        raise HTTPException(404, "AI 对话日志尚未生成")

    content = combined.read_text(encoding="utf-8")
    return {"content": content, "filename": combined.name}


@app.get("/api/ai-interactions/{session_id}")
async def list_ai_interactions(session_id: str):
    """列出 AI prompts 和 responses 文件清单及内容。"""
    log_dir = _find_log_dir(session_id)
    if log_dir is None:
        raise HTTPException(404, "未找到日志目录")

    prompts_dir = log_dir / "ai_prompts"
    responses_dir = log_dir / "ai_responses"

    files: list[dict] = []

    if prompts_dir.is_dir():
        for fname in sorted(os.listdir(prompts_dir)):
            if fname.endswith(".txt"):
                path = prompts_dir / fname
                files.append({
                    "name": fname,
                    "type": "prompt",
                    "content": path.read_text(encoding="utf-8"),
                })

    if responses_dir.is_dir():
        for fname in sorted(os.listdir(responses_dir)):
            if fname.endswith(".txt"):
                path = responses_dir / fname
                files.append({
                    "name": fname,
                    "type": "response",
                    "content": path.read_text(encoding="utf-8"),
                })

    return {"interactions": files, "count": len(files)}


# ── 清理 ──────────────────────────────────────────────────


async def _cleanup_after_download(session_id: str):
    """下载完成后延迟 5 分钟清理，避免干扰。"""
    await asyncio.sleep(300)
    work_dir = session_dirs.pop(session_id, None)
    session_queues.pop(session_id, None)
    session_zips.pop(session_id, None)
    if work_dir and work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)


async def _save_custom_templates_into(
    target_dir: Path,
    fpa_template: UploadFile | None,
    cosmic_template: UploadFile | None,
    list_template: UploadFile | None,
    spec_template: UploadFile | None,
):
    """将自定义模板保存到指定目录。"""
    for tpl_file, tpl_name in [
        (fpa_template, "FPA工作量评估-模板.xlsx"),
        (cosmic_template, "项目功能点拆分表-模板.xlsx"),
        (list_template, "项目需求清单-模板.xlsx"),
        (spec_template, "项目需求说明书-模板.docx"),
    ]:
        if tpl_file is not None and tpl_file.filename:
            tpl_content = await tpl_file.read()
            (target_dir / tpl_name).write_bytes(tpl_content)


async def _save_custom_templates(
    parent_dir: Path,
    fpa_template: UploadFile | None,
    cosmic_template: UploadFile | None,
    list_template: UploadFile | None,
    spec_template: UploadFile | None,
) -> str:
    """将自定义模板保存到临时目录，返回目录路径。"""
    custom_t_dir = parent_dir / "custom_templates"
    custom_t_dir.mkdir(parents=True, exist_ok=True)
    await _save_custom_templates_into(
        custom_t_dir, fpa_template, cosmic_template, list_template, spec_template
    )
    return str(custom_t_dir)


# ── 执行分发 ──────────────────────────────────────────────


def _execute_mode(
    mode: str,
    file_path: str,
    output_dir: str,
    custom_t_dir: str,
    api_key: str,
    model: str,
    base_url: str,
    project_name: str = "",
    max_tokens: str = "",
    clean: bool = False,
):
    """一站式管道入口，CLI / Web UI 共享。"""
    from ai_gen_reimbursement_docs.pipeline import run_pipeline_simple

    if max_tokens:
        os.environ["AI_REIMBURSEMENT_MAX_TOKENS"] = max_tokens
    if clean and os.path.isdir(output_dir):
        for name in os.listdir(output_dir):
            if name not in ("custom_templates",):
                path = os.path.join(output_dir, name)
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path, ignore_errors=True)

    logger = logging.getLogger("ai_gen_reimbursement_docs")
    logger.info(f"操作模式: {MODE_INFO.get(mode, {}).get('label', mode)}")

    pipeline_mode = _MODE_MAP[mode]
    templates = _build_templates_dict(custom_t_dir)

    return run_pipeline_simple(
        mode=pipeline_mode,
        file_path=file_path,
        output_dir=output_dir,
        api_key=api_key,
        model=model,
        base_url=base_url,
        project_name=project_name,
        templates=templates or None,
    )


def _build_templates_dict(custom_t_dir: str) -> dict[str, str]:
    """构建 templates dict：自定义模板优先。"""
    import glob as _glob

    templates: dict[str, str] = {}
    for key, glob_pat in [
        ("fpa", "FPA*评估*模板*.xlsx"),
        ("cosmic", "*功能点拆分表*模板*.xlsx"),
        ("list", "*需求清单*模板*.xlsx"),
        ("spec", "*需求说明书*模板*.docx"),
    ]:
        matches = _glob.glob(os.path.join(custom_t_dir, glob_pat))
        if matches:
            templates[key] = matches[0]
    return templates
