import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
FastAPI = pytest.importorskip("fastapi").FastAPI
Depends = pytest.importorskip("fastapi").Depends

from web_app.dependencies import require_auth


def test_remote_request_does_not_bypass_auth_when_work_mode_is_local(monkeypatch):
    monkeypatch.setattr(
        "ai_gen_reimbursement_docs.config_utils.load_web_work_mode",
        lambda: "local",
    )
    app = FastAPI()

    @app.get("/protected")
    async def protected(_user: str = Depends(require_auth)):
        return {"ok": True}

    client = TestClient(app, client=("203.0.113.10", 50000))

    resp = client.get("/protected")

    assert resp.status_code == 401
