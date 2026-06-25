import base64
import io

from fastapi.testclient import TestClient
from pptx import Presentation

from tests.fixtures.build import deck_with_issues


def _client(monkeypatch, password="secret"):
    monkeypatch.setenv("SLIDECHECK_PASSWORD", password)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # force NullDescriber
    from api.index import app
    return TestClient(app)


def _pptx(tmp_path):
    p = deck_with_issues(str(tmp_path / "d.pptx"))
    with open(p, "rb") as fh:
        return fh.read()


def test_health(monkeypatch):
    assert _client(monkeypatch).get("/api/health").json() == {"ok": True}


def test_process_requires_password(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    r = client.post("/api/process", files={"files": ("d.pptx", _pptx(tmp_path))})
    assert r.status_code == 401


def test_process_503_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv("SLIDECHECK_PASSWORD", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from api.index import app
    client = TestClient(app, raise_server_exceptions=True)
    r = client.post(
        "/api/process",
        files={"files": ("d.pptx", _pptx(tmp_path))},
        headers={"x-slidecheck-password": "anything"},
    )
    assert r.status_code == 503


def test_process_happy_path(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    r = client.post(
        "/api/process",
        files={"files": ("d.pptx", _pptx(tmp_path))},
        headers={"x-slidecheck-password": "secret"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["files"]) == 1
    f = body["files"][0]
    assert f["error"] is None
    assert f["report_html"]
    assert f["fixed_filename"].endswith("_accessible.pptx")
    Presentation(io.BytesIO(base64.b64decode(f["fixed_pptx_b64"])))


def test_process_rejects_non_pptx(monkeypatch):
    client = _client(monkeypatch)
    r = client.post(
        "/api/process",
        files={"files": ("notes.txt", b"hello")},
        headers={"x-slidecheck-password": "secret"},
    )
    assert r.status_code == 400


def test_process_rejects_oversize(monkeypatch):
    monkeypatch.setenv("SLIDECHECK_MAX_UPLOAD_MB", "0")  # any non-empty file is too big
    client = _client(monkeypatch)
    r = client.post(
        "/api/process",
        files={"files": ("d.pptx", b"x")},
        headers={"x-slidecheck-password": "secret"},
    )
    assert r.status_code == 413
