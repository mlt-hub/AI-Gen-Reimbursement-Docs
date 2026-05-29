import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel


class LicenseActivationRequest(BaseModel):
    license_path: str = ""
    license_text: str = ""
    license_secret: str
    data_enc: str = ""
    data_output: str = ""
    public_key: str = ""
    activation_path: str = ""


def _read_version(base_dir: Path) -> str:
    try:
        import tomllib

        toml = base_dir / "pyproject.toml"
        if toml.exists():
            return tomllib.load(toml.open("rb"))["project"]["version"]
    except Exception:
        pass
    return "unknown"


def _request_is_local(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost", "testclient")


def _resolved_work_mode(request: Request) -> str:
    from ai_gen_reimbursement_docs.config_utils import load_web_work_mode

    configured = load_web_work_mode()
    if configured in ("local", "remote"):
        return configured
    return "local" if _request_is_local(request) else "remote"


def _readable_directory(path: Path) -> bool:
    return path.exists() and path.is_dir()


def _license_paths(base_dir: Path, payload: LicenseActivationRequest | None = None) -> dict[str, Path]:
    return {
        "data_enc": Path(payload.data_enc).expanduser() if payload and payload.data_enc else base_dir / "data.enc",
        "data_output": Path(payload.data_output).expanduser() if payload and payload.data_output else base_dir / "data",
        "public_key": (
            Path(payload.public_key).expanduser()
            if payload and payload.public_key
            else base_dir / "ai_gen_reimbursement_docs" / "licensing" / "public_key.pem"
        ),
        "activation_path": (
            Path(payload.activation_path).expanduser()
            if payload and payload.activation_path
            else Path.home() / ".ai-gen-reimbursement-docs" / "license" / "activation.json"
        ),
    }


def create_router(*, base_dir: Path, mode_info: dict[str, dict[str, str]]) -> APIRouter:
    router = APIRouter()

    @router.get("/api/is-local")
    async def is_local(request: Request):
        """判断请求是否来自本机。"""
        return {"local": _request_is_local(request)}

    @router.get("/api/modes")
    async def get_modes():
        """返回操作模式列表，供前端动态渲染下拉框。"""
        return mode_info

    @router.get("/api/version")
    async def get_version():
        """返回当前版本号（从 pyproject.toml 读取）。"""
        return {"version": _read_version(base_dir)}

    @router.get("/api/health")
    async def health(request: Request):
        """返回 Web UI 需要的轻量健康检查信息。"""
        input_templates = base_dir / "data" / "in_templates"
        output_templates = base_dir / "data" / "out_templates"
        templates_readable = _readable_directory(input_templates) and _readable_directory(output_templates)

        return {
            "ok": templates_readable,
            "version": _read_version(base_dir),
            "work_mode": _resolved_work_mode(request),
            "api": {
                "version": True,
                "modes": True,
                "config": True,
                "license": True,
            },
            "paths": {
                "templates_readable": templates_readable,
                "output_writable": None,
            },
            "features": {
                "prompt_debug": True,
                "ai_interactions": True,
            },
        }

    @router.get("/api/license/status")
    async def license_status():
        """返回离线授权相关文件与激活状态。"""
        paths = _license_paths(base_dir)
        status = {
            "activated": False,
            "crypto_available": True,
            "data_package_present": paths["data_enc"].exists(),
            "public_key_present": paths["public_key"].exists(),
            "activation_metadata_present": paths["activation_path"].exists(),
            "paths": {
                "data_enc": str(paths["data_enc"]),
                "data_output": str(paths["data_output"]),
                "public_key": str(paths["public_key"]),
                "activation_metadata": str(paths["activation_path"]),
            },
        }
        if not paths["data_enc"].exists():
            return status
        try:
            from ai_gen_reimbursement_docs.licensing import is_activated
        except ModuleNotFoundError as exc:
            if exc.name == "cryptography":
                status["crypto_available"] = False
                return status
            raise
        status["activated"] = is_activated(paths["data_enc"], paths["data_output"])
        return status

    @router.post("/api/license/activate")
    async def license_activate(request: Request, payload: LicenseActivationRequest):
        """激活受保护数据包。"""
        if not _request_is_local(request):
            raise HTTPException(403, "仅本机模式支持离线激活")
        if not payload.license_path.strip() and not payload.license_text.strip():
            raise HTTPException(400, "缺少 license 文件或 license 内容")
        if not payload.license_secret.strip():
            raise HTTPException(400, "缺少 license secret")

        paths = _license_paths(base_dir, payload)
        license_path = Path(payload.license_path).expanduser() if payload.license_path.strip() else None
        if license_path is not None and not license_path.exists():
            raise HTTPException(400, f"license 文件不存在: {license_path}")
        if not paths["data_enc"].exists():
            raise HTTPException(400, f"data.enc 不存在: {paths['data_enc']}")
        if not paths["public_key"].exists():
            raise HTTPException(400, f"公钥文件不存在: {paths['public_key']}")

        try:
            from ai_gen_reimbursement_docs.licensing import activate, activate_verified_payload, load_public_key
            from ai_gen_reimbursement_docs.licensing.exceptions import LicensingError
            from ai_gen_reimbursement_docs.licensing.license_file import verify_license_doc
        except ModuleNotFoundError as exc:
            if exc.name == "cryptography":
                raise HTTPException(500, "激活功能需要安装依赖: cryptography>=41.0") from exc
            raise

        try:
            public_key = load_public_key(paths["public_key"])
            if payload.license_text.strip():
                license_doc = json.loads(payload.license_text)
                verified_payload = verify_license_doc(license_doc, public_key)
                result = activate_verified_payload(
                    payload=verified_payload,
                    secret=payload.license_secret,
                    data_enc=paths["data_enc"],
                    output_dir=paths["data_output"],
                    activation_path=paths["activation_path"],
                )
            elif license_path is not None:
                result = activate(
                    license_path=license_path,
                    secret=payload.license_secret,
                    data_enc=paths["data_enc"],
                    output_dir=paths["data_output"],
                    public_key=public_key,
                    activation_path=paths["activation_path"],
                )
            else:
                raise HTTPException(400, "缺少 license 文件或 license 内容")
        except LicensingError as exc:
            raise HTTPException(400, f"激活失败: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise HTTPException(400, "license 文件内容不是有效 JSON") from exc
        except Exception as exc:
            raise HTTPException(400, f"激活失败: {exc}") from exc

        return {
            "ok": True,
            "license_id": result.license_id,
            "customer": result.customer,
            "activation_path": str(result.activation_path),
            "data_output": str(paths["data_output"]),
        }

    @router.post("/api/play-notify")
    async def play_notify(request: Request):
        """播放完成提示音（仅本机模式生效）。"""
        host = request.client.host if request.client else ""
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise HTTPException(403, "仅本机模式支持提示音")
        from ai_gen_reimbursement_docs.cli.notify import play_notify_sound

        play_notify_sound()
        return {"ok": True}

    return router
