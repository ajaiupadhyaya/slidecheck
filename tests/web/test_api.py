import base64
import io
import json

import pytest
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


# ---------------------------------------------------------------------------
# /api/analyze
# ---------------------------------------------------------------------------

def test_analyze_happy_path(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    r = client.post(
        "/api/analyze",
        files={"files": ("d.pptx", _pptx(tmp_path))},
        headers={"x-slidecheck-password": "secret"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["files"]) == 1
    f = body["files"][0]
    assert f["error"] is None
    analysis = f["analysis"]
    assert "findings" in analysis
    assert "score" in analysis
    assert "coverage" in analysis
    # alt-text finding should carry a thumbnail
    alt_findings = [ff for ff in analysis["findings"] if ff.get("fix_action") == "set_alt_text"]
    assert alt_findings, "expected at least one alt-text finding from deck_with_issues"
    assert "thumbnail" in alt_findings[0], "alt-text finding should have a thumbnail"


def test_analyze_requires_password(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    r = client.post(
        "/api/analyze",
        files={"files": ("d.pptx", _pptx(tmp_path))},
        # no x-slidecheck-password header
    )
    assert r.status_code == 401


def test_analyze_503_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv("SLIDECHECK_PASSWORD", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from api.index import app
    client = TestClient(app, raise_server_exceptions=True)
    r = client.post(
        "/api/analyze",
        files={"files": ("d.pptx", _pptx(tmp_path))},
        headers={"x-slidecheck-password": "anything"},
    )
    assert r.status_code == 503


def test_analyze_rejects_non_pptx(monkeypatch):
    client = _client(monkeypatch)
    r = client.post(
        "/api/analyze",
        files={"files": ("notes.txt", b"hello")},
        headers={"x-slidecheck-password": "secret"},
    )
    assert r.status_code == 400


def test_analyze_rejects_oversize(monkeypatch):
    monkeypatch.setenv("SLIDECHECK_MAX_UPLOAD_MB", "0")  # any non-empty file is too big
    client = _client(monkeypatch)
    r = client.post(
        "/api/analyze",
        files={"files": ("d.pptx", b"x")},
        headers={"x-slidecheck-password": "secret"},
    )
    assert r.status_code == 413


# ---------------------------------------------------------------------------
# /api/export
# ---------------------------------------------------------------------------

def test_export_applies_plan(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    pptx_bytes = _pptx(tmp_path)

    # Analyze first to obtain a real target from the findings
    r = client.post(
        "/api/analyze",
        files={"files": ("d.pptx", pptx_bytes)},
        headers={"x-slidecheck-password": "secret"},
    )
    assert r.status_code == 200
    findings = r.json()["files"][0]["analysis"]["findings"]
    alt_finding = next(
        (f for f in findings if f.get("fix_action") == "set_alt_text"),
        None,
    )
    assert alt_finding is not None, "deck_with_issues must produce an alt-text finding"

    plan = [{"action": "set_alt_text", "target": alt_finding["target"], "value": "A descriptive alt text"}]

    r = client.post(
        "/api/export",
        files={"files": ("d.pptx", pptx_bytes)},
        data={"plan": json.dumps(plan)},
        headers={"x-slidecheck-password": "secret"},
    )
    assert r.status_code == 200
    result = r.json()["files"][0]
    assert result["error"] is None
    assert result["fixed_pptx_b64"] is not None

    fixed_bytes = base64.b64decode(result["fixed_pptx_b64"])
    prs = Presentation(io.BytesIO(fixed_bytes))

    # Verify the alt text was actually applied
    from pptx_a11y.refs import resolve_target
    shape = resolve_target(prs, alt_finding["target"])
    assert shape is not None
    assert shape._element._nvXxPr.cNvPr.get("descr") == "A descriptive alt text"


def test_export_bad_plan_400(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    r = client.post(
        "/api/export",
        files={"files": ("d.pptx", _pptx(tmp_path))},
        data={"plan": '{"not": "a list"}'},
        headers={"x-slidecheck-password": "secret"},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# _check_password contract
# ---------------------------------------------------------------------------

def test_check_password_non_ascii_returns_401_not_500(monkeypatch):
    from fastapi import HTTPException
    from starlette.requests import Request

    from api.index import _check_password

    monkeypatch.setenv("SLIDECHECK_PASSWORD", "café-secret")  # non-ASCII configured pw
    scope = {
        "type": "http",
        "headers": [(b"x-slidecheck-password", "wröng".encode("latin-1"))],
    }
    with pytest.raises(HTTPException) as exc_info:
        _check_password(Request(scope))
    assert exc_info.value.status_code == 401  # clean 401, not a TypeError/500
