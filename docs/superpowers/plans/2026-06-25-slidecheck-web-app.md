# SlideCheck Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the existing `pptx_a11y` accessibility engine in a Vercel-hosted web app so a non-technical user on a locked-down machine can fix PowerPoint accessibility in the browser with zero install.

**Architecture:** A thin, framework-agnostic web service (`pptx_a11y/web/`) turns uploaded `.pptx` bytes into reports + fixed files entirely inside a temp dir; a FastAPI app (`api/index.py`) exposes it as a Vercel Python function behind a shared-password gate; a static page (`public/`) provides drag-drop upload and in-browser downloads. The accessibility engine is reused unchanged except for reading the Claude key from an env var.

**Tech Stack:** Python 3.12, FastAPI + python-multipart (web), python-pptx + pillow + anthropic (engine, unchanged), plain HTML/CSS/JS (front end), Vercel (hosting), uv (tooling), pytest (tests), Playwright (e2e verification).

## Global Constraints

- Python `>=3.12` (matches `pyproject.toml`).
- Use **uv** for all Python commands: `uv run pytest`, `uv add`, `uv sync` — never bare `pip`/`python`.
- **Do not modify the accessibility engine's behavior.** The only engine change allowed is reading `ANTHROPIC_API_KEY` from the environment in `settings.get_describer`. The CLI, Tkinter GUI, and all existing tests must keep passing.
- **Originals are never modified** — the engine already writes a `*_accessible.pptx` copy; preserve that guarantee.
- The web runtime must **not** depend on `tkinterdnd2` (GUI-only). The web import path touches only `pipeline`/`checks`/`fixers`/`report`/`settings`/`alt_text_ai`/`web`.
- **Nothing persists**: every request processes in a `tempfile.TemporaryDirectory` and returns a self-contained response; no disk persistence, no database, no cross-request server memory.
- All env-derived limits (`SLIDECHECK_PASSWORD`, `SLIDECHECK_MAX_UPLOAD_MB`, `SLIDECHECK_MAX_AI_IMAGES`) are read **at request time**, not at import, so they are testable and runtime-configurable.
- Copy shown to the user must be plain language (the user is a non-technical professor).

---

### Task 1: Read the Claude key from the environment

Lets the web app supply the API key as a server secret without the user ever handling a key. Desktop behavior is unchanged because the env var is absent there.

**Files:**
- Modify: `pptx_a11y/settings.py` (the `get_describer` function)
- Test: `tests/test_settings.py`

**Interfaces:**
- Consumes: `ClaudeDescriber`, `NullDescriber` from `pptx_a11y.alt_text_ai` (existing).
- Produces: `get_describer(settings: dict)` — precedence: `settings["api_key"]` → `os.environ["ANTHROPIC_API_KEY"]` → `NullDescriber`. Returns a `ClaudeDescriber` when any key is present, else `NullDescriber`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_settings.py` (add imports at top if missing):

```python
from pptx_a11y.alt_text_ai import ClaudeDescriber, NullDescriber
from pptx_a11y.settings import get_describer


def test_get_describer_uses_env_key_when_settings_empty(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
    d = get_describer({})
    assert isinstance(d, ClaudeDescriber)
    assert d._api_key == "sk-from-env"


def test_settings_key_takes_precedence_over_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
    d = get_describer({"api_key": "sk-from-settings"})
    assert isinstance(d, ClaudeDescriber)
    assert d._api_key == "sk-from-settings"


def test_no_key_anywhere_is_null_describer(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(get_describer({}), NullDescriber)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_settings.py -k "env or precedence or null" -v`
Expected: `test_get_describer_uses_env_key_when_settings_empty` FAILS (env key ignored → returns `NullDescriber`).

- [ ] **Step 3: Implement the env fallback**

In `pptx_a11y/settings.py`, replace the body of `get_describer`:

```python
def get_describer(settings: dict):
    key = (settings.get("api_key") or os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    return ClaudeDescriber(key) if key else NullDescriber()
```

(`os` is already imported in this file.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_settings.py -v`
Expected: PASS (all settings tests, old and new).

- [ ] **Step 5: Commit**

```bash
git add pptx_a11y/settings.py tests/test_settings.py
git commit -m "feat(web): read ANTHROPIC_API_KEY from env in get_describer"
```

---

### Task 2: CappedDescriber — bound AI calls per request

On serverless hosts a deck with many images could exceed the function time limit. This wrapper describes up to N images, then returns `None` for the rest so they are flagged (not auto-described). Slide-title `suggest_text` is always delegated (cheap, not the timeout risk).

**Files:**
- Create: `pptx_a11y/web/__init__.py` (empty package marker)
- Create: `pptx_a11y/web/describers.py`
- Create: `tests/web/__init__.py` (empty package marker)
- Test: `tests/web/test_describers.py`

**Interfaces:**
- Consumes: the `Describer` protocol from `pptx_a11y.alt_text_ai` (`describe(image_bytes, media_type, context) -> str | None`, `suggest_text(prompt) -> str | None`).
- Produces: `CappedDescriber(inner, max_images: int)` — itself satisfies the `Describer` protocol; caps only `describe`.

- [ ] **Step 1: Create the package markers**

Create `pptx_a11y/web/__init__.py` with a single line:

```python
"""Web front-end glue for SlideCheck (no Tkinter, no Vercel specifics)."""
```

Create `tests/web/__init__.py` as an empty file:

```python
```

- [ ] **Step 2: Write the failing tests**

Create `tests/web/test_describers.py`:

```python
from pptx_a11y.web.describers import CappedDescriber


class _Counting:
    def __init__(self):
        self.describe_calls = 0
        self.suggest_calls = 0

    def describe(self, image_bytes, media_type, context):
        self.describe_calls += 1
        return f"alt-{self.describe_calls}"

    def suggest_text(self, prompt):
        self.suggest_calls += 1
        return "a title"


def test_caps_image_descriptions():
    inner = _Counting()
    capped = CappedDescriber(inner, max_images=2)
    assert capped.describe(b"x", "image/png", "c") == "alt-1"
    assert capped.describe(b"x", "image/png", "c") == "alt-2"
    assert capped.describe(b"x", "image/png", "c") is None  # over the cap
    assert inner.describe_calls == 2


def test_suggest_text_always_delegates():
    inner = _Counting()
    capped = CappedDescriber(inner, max_images=0)
    assert capped.suggest_text("p") == "a title"
    assert inner.suggest_calls == 1
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_describers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pptx_a11y.web.describers'`.

- [ ] **Step 4: Implement CappedDescriber**

Create `pptx_a11y/web/describers.py`:

```python
"""Describer wrappers used only by the web front end."""


class CappedDescriber:
    """Delegate to ``inner`` for the first ``max_images`` image descriptions,
    then return None so further images are flagged rather than auto-described.

    This keeps a single web request bounded in wall-clock time on serverless
    hosts. ``suggest_text`` (slide titles) is always delegated because it is
    cheap and not the timeout risk.
    """

    def __init__(self, inner, max_images: int):
        self._inner = inner
        self._max = max_images
        self._used = 0

    def describe(self, image_bytes: bytes, media_type: str, context: str) -> str | None:
        if self._used >= self._max:
            return None
        self._used += 1
        return self._inner.describe(image_bytes, media_type, context)

    def suggest_text(self, prompt: str) -> str | None:
        return self._inner.suggest_text(prompt)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/web/test_describers.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add pptx_a11y/web/__init__.py pptx_a11y/web/describers.py tests/web/__init__.py tests/web/test_describers.py
git commit -m "feat(web): CappedDescriber to bound AI calls per request"
```

---

### Task 3: Web service — process uploaded bytes into reports + fixed files

The framework-agnostic core of the web app. Knows nothing about HTTP. Takes `(filename, bytes)` uploads, runs the engine in a temp dir, and returns rendered report HTML + fixed-file bytes. The temp dir is deleted before returning, so nothing persists.

**Files:**
- Create: `pptx_a11y/web/service.py`
- Test: `tests/web/test_service.py`

**Interfaces:**
- Consumes: `process_file(path, describer, out_dir)` (→ `FileResult` with `.error`, `.output_path`, `.findings`), `summary_counts(result) -> dict`, `html_report.render(result) -> str` — all from `pptx_a11y`. The `FileResult.output_path` points at the saved `*_accessible.pptx`.
- Produces:
  - `FileOutput` dataclass: `filename: str`, `error: str | None`, `summary: dict`, `report_html: str | None`, `fixed_filename: str | None`, `fixed_bytes: bytes | None`.
  - `WebResult` dataclass: `files: list[FileOutput]`.
  - `process_uploads(uploads: list[tuple[str, bytes]], describer) -> WebResult`.

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_service.py`:

```python
import io
import os

from pptx import Presentation

from pptx_a11y.alt_text_ai import NullDescriber
from pptx_a11y.web.service import process_uploads
from tests.fixtures.build import clean_deck, deck_with_issues


def _bytes(tmp_path, builder, name="src.pptx"):
    p = builder(str(tmp_path / name))
    with open(p, "rb") as fh:
        return fh.read()


def test_single_upload_returns_report_and_valid_fixed_file(tmp_path):
    data = _bytes(tmp_path, deck_with_issues)
    res = process_uploads([("lecture.pptx", data)], NullDescriber())
    assert len(res.files) == 1
    out = res.files[0]
    assert out.error is None
    assert out.report_html and "<" in out.report_html
    assert out.fixed_filename.endswith("_accessible.pptx")
    assert out.fixed_bytes
    Presentation(io.BytesIO(out.fixed_bytes))  # valid pptx, no exception
    assert out.summary["error"] >= 1  # planted missing-title / alt-text errors


def test_batch_upload_returns_one_output_per_file(tmp_path):
    a = _bytes(tmp_path, clean_deck, "a.pptx")
    b = _bytes(tmp_path, deck_with_issues, "b.pptx")
    res = process_uploads([("a.pptx", a), ("b.pptx", b)], NullDescriber())
    assert [o.filename for o in res.files] == ["a.pptx", "b.pptx"]
    assert all(o.error is None for o in res.files)


def test_corrupt_upload_surfaces_error(tmp_path):
    res = process_uploads([("broken.pptx", b"definitely not a pptx")], NullDescriber())
    assert len(res.files) == 1
    assert res.files[0].error
    assert res.files[0].fixed_bytes is None


def test_processing_leaves_no_files_in_cwd(tmp_path, monkeypatch):
    data = _bytes(tmp_path, clean_deck, "kept.pptx")
    monkeypatch.chdir(tmp_path)
    process_uploads([("d.pptx", data)], NullDescriber())
    leftover = sorted(n for n in os.listdir(tmp_path) if n.endswith((".pptx", ".html", ".json")))
    assert leftover == ["kept.pptx"]  # only the fixture, no engine artifacts
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pptx_a11y.web.service'`.

- [ ] **Step 3: Implement the service**

Create `pptx_a11y/web/service.py`:

```python
"""Turn uploaded .pptx bytes into reports + fixed files, entirely inside a
TemporaryDirectory that is deleted before returning. Nothing is persisted.
"""
import os
import tempfile
from dataclasses import dataclass, field

from pptx_a11y.pipeline import process_file
from pptx_a11y.report import html_report, summary_counts


@dataclass
class FileOutput:
    filename: str
    error: str | None = None
    summary: dict = field(default_factory=dict)
    report_html: str | None = None
    fixed_filename: str | None = None
    fixed_bytes: bytes | None = None


@dataclass
class WebResult:
    files: list[FileOutput]


def _stem(name: str) -> str:
    return os.path.splitext(os.path.basename(name))[0] or "upload"


def process_uploads(uploads: list[tuple[str, bytes]], describer) -> WebResult:
    """uploads: list of (original_filename, file_bytes). Returns one FileOutput
    per upload with rendered report HTML and fixed-file bytes."""
    outputs: list[FileOutput] = []
    with tempfile.TemporaryDirectory() as tmp:
        for filename, data in uploads:
            in_path = os.path.join(tmp, f"{_stem(filename)}.pptx")
            with open(in_path, "wb") as fh:
                fh.write(data)
            result = process_file(in_path, describer, out_dir=tmp)
            if result.error:
                outputs.append(FileOutput(filename=filename, error=result.error))
                continue
            with open(result.output_path, "rb") as fh:
                fixed_bytes = fh.read()
            outputs.append(
                FileOutput(
                    filename=filename,
                    summary=summary_counts(result),
                    report_html=html_report.render(result),
                    fixed_filename=os.path.basename(result.output_path),
                    fixed_bytes=fixed_bytes,
                )
            )
    return WebResult(files=outputs)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/web/test_service.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add pptx_a11y/web/service.py tests/web/test_service.py
git commit -m "feat(web): process_uploads service (temp-dir, ephemeral, no persistence)"
```

---

### Task 4: FastAPI app — `/api/process` with password gate and validation

The HTTP layer exposed to Vercel as a Python function. Adds web/test deps, the FastAPI app, the password gate, upload validation, and the JSON response carrying everything inline. Also configures pytest's path so `api` and `tests` import cleanly.

**Files:**
- Create: `api/index.py`
- Modify: `pyproject.toml` (add `[tool.pytest.ini_options] pythonpath = ["."]`; add dev deps)
- Test: `tests/web/test_api.py`

**Interfaces:**
- Consumes: `get_describer` (Task 1), `CappedDescriber` (Task 2), `process_uploads` + `WebResult`/`FileOutput` (Task 3).
- Produces: ASGI app object named `app` (required by the Vercel Python runtime). Endpoints:
  - `GET /api/health` → `{"ok": true}`.
  - `POST /api/process` (multipart, form field `files`, header `x-slidecheck-password`) → `{"files": [{filename, error, summary, report_html, fixed_filename, fixed_pptx_b64}]}`.
  - Status codes: `503` if `SLIDECHECK_PASSWORD` unset, `401` wrong/missing password, `400` non-pptx / no files, `413` over size cap.

- [ ] **Step 1: Add web + test dependencies (dev group)**

Run:

```bash
cd ~/Documents/slidecheck && uv add --dev fastapi "python-multipart>=0.0.9" uvicorn httpx
```

(`fastapi` brings `starlette`; `httpx` is required by `fastapi.testclient.TestClient`; `uvicorn` is for local dev in Task 5. These are dev-only — Vercel installs its own runtime set in Task 6's `requirements.txt`.)

- [ ] **Step 2: Add the pytest path config**

Append to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

- [ ] **Step 3: Write the failing tests**

Create `tests/web/test_api.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'api'`.

- [ ] **Step 5: Implement the FastAPI app**

Create `api/index.py`:

```python
"""SlideCheck web API — exposed to Vercel as a Python (ASGI) function.

On Vercel the platform serves the static front end in ``public/`` and routes
only ``/api/*`` to this function; the StaticFiles mount below is therefore inert
on Vercel and exists so a single ``uvicorn api.index:app`` serves everything in
local development.
"""
import base64
import hmac
import os

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from pptx_a11y.settings import get_describer
from pptx_a11y.web.describers import CappedDescriber
from pptx_a11y.web.service import process_uploads

app = FastAPI(title="SlideCheck")


def _max_upload_bytes() -> int:
    return int(os.environ.get("SLIDECHECK_MAX_UPLOAD_MB", "50")) * 1024 * 1024


def _max_ai_images() -> int:
    return int(os.environ.get("SLIDECHECK_MAX_AI_IMAGES", "40"))


def _check_password(request: Request) -> None:
    expected = os.environ.get("SLIDECHECK_PASSWORD")
    if not expected:
        raise HTTPException(status_code=503, detail="Server not configured: set SLIDECHECK_PASSWORD.")
    provided = request.headers.get("x-slidecheck-password", "")
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Wrong or missing password.")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/process")
async def process(request: Request, files: list[UploadFile]):
    _check_password(request)
    limit = _max_upload_bytes()
    mb = limit // (1024 * 1024)
    uploads: list[tuple[str, bytes]] = []
    for f in files:
        name = f.filename or "upload.pptx"
        if not name.lower().endswith(".pptx"):
            raise HTTPException(status_code=400, detail=f"Not a PowerPoint (.pptx) file: {name}")
        data = await f.read()
        if len(data) > limit:
            raise HTTPException(status_code=413, detail=f"{name} is larger than the {mb} MB limit.")
        uploads.append((name, data))
    if not uploads:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    describer = CappedDescriber(get_describer({}), _max_ai_images())
    result = process_uploads(uploads, describer)

    payload = [
        {
            "filename": out.filename,
            "error": out.error,
            "summary": out.summary,
            "report_html": out.report_html,
            "fixed_filename": out.fixed_filename,
            "fixed_pptx_b64": (
                base64.b64encode(out.fixed_bytes).decode("ascii") if out.fixed_bytes else None
            ),
        }
        for out in result.files
    ]
    return JSONResponse({"files": payload})


# Local dev / e2e only — registered last so the /api routes match first.
_PUBLIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
if os.path.isdir(_PUBLIC):
    app.mount("/", StaticFiles(directory=_PUBLIC, html=True), name="static")
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/web/test_api.py -v`
Expected: PASS (6 tests). Note: the StaticFiles mount only registers once `public/` exists (Task 5); until then it is skipped, which is fine.

- [ ] **Step 7: Run the full suite to confirm no regressions**

Run: `uv run pytest -q`
Expected: PASS (all prior 72 engine tests + the new web tests).

- [ ] **Step 8: Commit**

```bash
git add api/index.py pyproject.toml uv.lock tests/web/test_api.py
git commit -m "feat(web): FastAPI /api/process with password gate and validation"
```

---

### Task 5: Static front end — upload, report, in-browser downloads

One framework-free page: password gate → drag-drop → spinner → friendly summary + inline report (iframe) + download buttons built from the base64 bytes in the response. Verified end-to-end with Playwright against a local server (no JS test runner in this repo).

**Files:**
- Create: `public/index.html`
- Create: `public/styles.css`
- Create: `public/app.js`

**Interfaces:**
- Consumes: `POST /api/process` (form field `files`, header `x-slidecheck-password`) → `{"files": [{filename, error, summary, report_html, fixed_filename, fixed_pptx_b64}]}`; `GET /api/health`.
- Produces: no code interface (browser UI). `summary` keys used: `error`, `warning`, `info`, `auto_fixed`, `manual` (from `summary_counts`).

- [ ] **Step 1: Create `public/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SlideCheck — PowerPoint accessibility</title>
  <link rel="stylesheet" href="/styles.css" />
</head>
<body>
  <main>
    <h1>SlideCheck</h1>
    <p class="tagline">Check and auto-fix PowerPoint accessibility. Your original file is never changed — you get a fixed copy.</p>

    <section id="gate" hidden>
      <label for="password">Enter the access password</label>
      <div class="gate-row">
        <input id="password" type="password" autocomplete="current-password" />
        <button id="unlock" type="button">Continue</button>
      </div>
      <p id="gate-error" class="error" role="alert"></p>
    </section>

    <section id="app" hidden>
      <div id="dropzone" tabindex="0" role="button" aria-label="Drop PowerPoint files here or click to choose">
        <p><strong>Drop your PowerPoint here</strong></p>
        <p class="muted">or click to choose a .pptx file (you can pick several)</p>
        <input id="file-input" type="file" accept=".pptx" multiple hidden />
      </div>
      <p id="status" class="status" role="status"></p>
      <div id="results"></div>
    </section>
  </main>
  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `public/styles.css`**

```css
:root { --ink:#1a1a1a; --muted:#666; --line:#e0e0e0; --accent:#174ea6; --err:#a3140b; --ok:#137333; }
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, Arial, sans-serif; color: var(--ink); margin: 0; background: #fafafa; }
main { max-width: 820px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
h1 { font-size: 1.6rem; margin-bottom: .25rem; }
.tagline { color: var(--muted); margin-top: 0; }
.muted { color: var(--muted); }
.error { color: var(--err); }
.gate-row { display: flex; gap: .5rem; max-width: 420px; }
input[type=password] { flex: 1; padding: .55rem .6rem; border: 1px solid var(--line); border-radius: 6px; font-size: 1rem; }
button { padding: .55rem .9rem; border: 0; border-radius: 6px; background: var(--accent); color: #fff; font-size: 1rem; cursor: pointer; }
button:hover { background: #0f3d85; }
#dropzone { border: 2px dashed #bbb; border-radius: 12px; padding: 2.5rem 1rem; text-align: center; background: #fff; cursor: pointer; transition: border-color .15s, background .15s; }
#dropzone.drag { border-color: var(--accent); background: #eef3fb; }
#dropzone:focus { outline: 3px solid #bcd0f7; }
.status { min-height: 1.4rem; font-weight: 600; }
.file-card { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 1rem 1.1rem; margin-top: 1.1rem; }
.file-card h2 { font-size: 1.1rem; margin: 0 0 .35rem; }
.badges { display: flex; flex-wrap: wrap; gap: .4rem; margin: .25rem 0 .75rem; }
.badge { font-size: .8rem; padding: .15rem .5rem; border-radius: 999px; background: #f0f0f0; }
.badge.err { background: #fbe6e4; color: var(--err); }
.badge.ok { background: #e3f1e7; color: var(--ok); }
.downloads { display: flex; flex-wrap: wrap; gap: .5rem; margin-bottom: .75rem; }
.report-frame { width: 100%; height: 360px; border: 1px solid var(--line); border-radius: 8px; }
.overview { width: 100%; border-collapse: collapse; margin-top: 1rem; }
.overview th, .overview td { text-align: left; padding: .45rem .6rem; border-bottom: 1px solid var(--line); }
.overview td.num { text-align: right; font-variant-numeric: tabular-nums; }
```

- [ ] **Step 3: Create `public/app.js`**

```javascript
const PW_KEY = "slidecheck-password";
const $ = (id) => document.getElementById(id);

function showApp() { $("gate").hidden = true; $("app").hidden = false; }
function showGate(msg) {
  $("app").hidden = true; $("gate").hidden = false;
  $("gate-error").textContent = msg || "";
}

function init() {
  if (sessionStorage.getItem(PW_KEY)) showApp(); else showGate("");
  $("unlock").addEventListener("click", () => {
    const pw = $("password").value.trim();
    if (!pw) { $("gate-error").textContent = "Please enter the password."; return; }
    sessionStorage.setItem(PW_KEY, pw);
    showApp();
  });
  $("password").addEventListener("keydown", (e) => { if (e.key === "Enter") $("unlock").click(); });

  const dz = $("dropzone"), input = $("file-input");
  dz.addEventListener("click", () => input.click());
  dz.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
  input.addEventListener("change", () => { if (input.files.length) upload(input.files); });
  ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", (e) => { if (e.dataTransfer.files.length) upload(e.dataTransfer.files); });
}

async function upload(fileList) {
  const files = [...fileList].filter((f) => f.name.toLowerCase().endsWith(".pptx"));
  if (!files.length) { $("status").textContent = "Please choose a PowerPoint (.pptx) file."; return; }
  $("results").innerHTML = "";
  $("status").textContent = files.length > 1
    ? `Checking ${files.length} files… generating alt text…`
    : "Checking your slides… generating alt text…";

  const fd = new FormData();
  files.forEach((f) => fd.append("files", f, f.name));
  let resp;
  try {
    resp = await fetch("/api/process", {
      method: "POST",
      headers: { "x-slidecheck-password": sessionStorage.getItem(PW_KEY) || "" },
      body: fd,
    });
  } catch {
    $("status").textContent = "Could not reach the server. Please try again.";
    return;
  }

  if (resp.status === 401) { sessionStorage.removeItem(PW_KEY); showGate("That password didn't work. Try again."); $("status").textContent = ""; return; }
  if (!resp.ok) {
    let detail = `Something went wrong (error ${resp.status}).`;
    try { const j = await resp.json(); if (j.detail) detail = j.detail; } catch {}
    $("status").textContent = detail;
    return;
  }

  const data = await resp.json();
  $("status").textContent = "Done.";
  render(data.files);
}

function render(files) {
  const root = $("results");
  if (files.length > 1) root.appendChild(overviewTable(files));
  files.forEach((f) => root.appendChild(fileCard(f)));
}

function overviewTable(files) {
  const t = document.createElement("table");
  t.className = "overview";
  t.innerHTML = "<thead><tr><th>File</th><th>Errors</th><th>Warnings</th><th>Auto-fixed</th><th>Needs manual fix</th></tr></thead>";
  const body = document.createElement("tbody");
  files.forEach((f) => {
    const s = f.summary || {};
    const row = document.createElement("tr");
    if (f.error) {
      row.innerHTML = `<td>${esc(f.filename)}</td><td colspan="4" class="error">Could not process: ${esc(f.error)}</td>`;
    } else {
      row.innerHTML = `<td>${esc(f.filename)}</td><td class="num">${s.error || 0}</td><td class="num">${s.warning || 0}</td><td class="num">${s.auto_fixed || 0}</td><td class="num">${s.manual || 0}</td>`;
    }
    body.appendChild(row);
  });
  t.appendChild(body);
  return t;
}

function fileCard(f) {
  const card = document.createElement("div");
  card.className = "file-card";
  const h = document.createElement("h2");
  h.textContent = f.filename;
  card.appendChild(h);

  if (f.error) {
    const p = document.createElement("p");
    p.className = "error";
    p.textContent = `Could not process this file: ${f.error}`;
    card.appendChild(p);
    return card;
  }

  const s = f.summary || {};
  const issues = (s.error || 0) + (s.warning || 0);
  const badges = document.createElement("div");
  badges.className = "badges";
  badges.innerHTML =
    `<span class="badge ${issues ? "err" : "ok"}">${issues} issue(s) found</span>` +
    `<span class="badge ok">${s.auto_fixed || 0} auto-fixed</span>` +
    `<span class="badge">${s.manual || 0} need a manual fix</span>`;
  card.appendChild(badges);

  const dl = document.createElement("div");
  dl.className = "downloads";
  dl.appendChild(downloadButton(
    "Download fixed PowerPoint", f.fixed_filename,
    b64ToBlob(f.fixed_pptx_b64, "application/vnd.openxmlformats-officedocument.presentationml.presentation")));
  dl.appendChild(downloadButton(
    "Download report", reportName(f.filename),
    new Blob([f.report_html], { type: "text/html" })));
  card.appendChild(dl);

  const frame = document.createElement("iframe");
  frame.className = "report-frame";
  frame.title = `Accessibility report for ${f.filename}`;
  frame.srcdoc = f.report_html;
  card.appendChild(frame);
  return card;
}

function downloadButton(label, filename, blob) {
  const a = document.createElement("a");
  a.textContent = label;
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.className = "download";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = label;
  btn.addEventListener("click", () => a.click());
  return btn;
}

function reportName(filename) {
  return filename.replace(/\.pptx$/i, "") + "_a11y_report.html";
}
function b64ToBlob(b64, type) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type });
}
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

init();
```

- [ ] **Step 4: Start a local server for end-to-end verification**

Run (background): `SLIDECHECK_PASSWORD=testpw uv run uvicorn api.index:app --port 8123`
(Leave `ANTHROPIC_API_KEY` unset so the run uses `NullDescriber` and needs no real key.)
Confirm it serves: `curl -s localhost:8123/api/health` → `{"ok":true}`.

- [ ] **Step 5: Drive the app with Playwright (manual e2e gate)**

Using the Playwright MCP browser tools:
1. Navigate to `http://localhost:8123/`.
2. Assert the password gate is visible; type `testpw`; click **Continue**.
3. Build a fixture deck locally for upload, e.g.:
   `uv run python -c "from tests.fixtures.build import deck_with_issues; deck_with_issues('/private/tmp/claude-501/-Users-ajaiupadhyaya/ad0691ca-219f-4f4a-91cf-f2ec0db19600/scratchpad/demo.pptx')"`
4. Upload that file via the `#file-input` (file chooser).
5. Assert: status shows "Done.", a file card appears with issue/auto-fixed badges, the inline report iframe renders, and the **Download fixed PowerPoint** + **Download report** buttons are present.
6. Stop the background server.

Expected: all assertions pass. (If the page is blank, check the browser console for the `/api/process` response and fix.)

- [ ] **Step 6: Commit**

```bash
git add public/index.html public/styles.css public/app.js
git commit -m "feat(web): static front end (upload, inline report, downloads)"
```

---

### Task 6: Vercel config, deploy, and docs

Make the function deployable, deploy a preview, verify it live, then production. Secrets (`ANTHROPIC_API_KEY`, `SLIDECHECK_PASSWORD`) are set by the user in Vercel — never committed.

**Files:**
- Create: `vercel.json`
- Create: `requirements.txt` (Vercel runtime deps — no `tkinterdnd2`, no dev-only deps)
- Create: `.vercelignore`
- Modify: `README.md` (add a "Web app" section)

**Interfaces:**
- Consumes: `api/index.py` exporting `app`; `pptx_a11y/**` engine source; `public/**` static assets.
- Produces: a deployed URL serving `public/index.html` at `/` and the function at `/api/*`.

- [ ] **Step 1: Create `requirements.txt` (Vercel function runtime deps)**

```
fastapi>=0.115
python-multipart>=0.0.9
python-pptx>=1.0.2
pillow>=12.2.0
anthropic>=0.111.0
```

(No `tkinterdnd2` — GUI only. No `uvicorn`/`httpx` — Vercel provides the ASGI server; those stay dev-only.)

- [ ] **Step 2: Create `vercel.json`**

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": {
    "api/index.py": {
      "maxDuration": 60,
      "memory": 1024,
      "includeFiles": "pptx_a11y/**"
    }
  }
}
```

(`includeFiles` bundles the engine source into the function so `import pptx_a11y` resolves. `maxDuration` 60s covers a typical lecture deck; the `CappedDescriber` from Task 2 bounds the worst case.)

- [ ] **Step 3: Create `.vercelignore`**

```
.venv
tests
dist
build
*.egg-info
docs
packaging
.pytest_cache
```

(Keeps the function bundle small; `pptx_a11y/**` is force-included via `vercel.json`.)

- [ ] **Step 4: Verify Vercel Python config against current docs**

Before deploying, confirm the ASGI-`app` entrypoint, `includeFiles`, Python version (3.12), and `requirements.txt` behavior against current Vercel docs (use the `vercel:vercel-functions` / `vercel:nextjs` skills or `mcp__plugin_vercel__search_vercel_documentation`). Adjust `vercel.json` if the platform expects a different shape (e.g. a `runtime`/`config` key for the Python version).

- [ ] **Step 5: Deploy a PREVIEW and set env vars**

This is outward-facing — **pause and confirm with the user**, and have the user supply the secrets (do not put them in the repo). Steps:
1. Deploy a preview from the branch (Vercel MCP `deploy_to_vercel`, or `vercel` CLI: `vercel` for preview).
2. Have the user set project env vars in Vercel (Production + Preview): `ANTHROPIC_API_KEY` (their funded Claude key) and `SLIDECHECK_PASSWORD` (a password they choose). Optionally `SLIDECHECK_MAX_UPLOAD_MB`, `SLIDECHECK_MAX_AI_IMAGES`.
3. Redeploy so the env vars take effect.

- [ ] **Step 6: Verify the live preview**

1. `curl -s <preview-url>/api/health` → `{"ok":true}` (proves the function boots and FastAPI installed).
2. With Playwright MCP: open the preview URL, enter the password, upload the fixture deck (`deck_with_issues`), and confirm the report renders + both downloads work. This exercises the real Claude key end-to-end (alt text is actually generated).

If `import pptx_a11y` fails in the function logs, fall back: add the local package to `requirements.txt` (append a line `.`) and move `tkinterdnd2` to an optional extra in `pyproject.toml` (`[project.optional-dependencies] gui = ["tkinterdnd2>=0.5.0"]`) so the server install excludes it; update the desktop build to install the `gui` extra. Re-deploy and re-verify.

- [ ] **Step 7: Add the README "Web app" section**

Add to `README.md` after the "Use it" section:

```markdown
## Web app (no install)

SlideCheck also runs as a web app — open the URL, enter the access password,
and drop your `.pptx` files in the browser. You get a fixed copy and a report
to download. Files are processed in memory and never stored.

- Hosting: Vercel (static front end in `public/`, Python function in `api/`).
- Configuration (Vercel project env vars): `ANTHROPIC_API_KEY` (server-side
  Claude key for AI alt text), `SLIDECHECK_PASSWORD` (the access password).
  Optional: `SLIDECHECK_MAX_UPLOAD_MB` (default 50), `SLIDECHECK_MAX_AI_IMAGES`
  (default 40).
- Local dev: `SLIDECHECK_PASSWORD=dev uv run uvicorn api.index:app --reload`
  then open http://localhost:8000.
```

- [ ] **Step 8: Promote to production and confirm**

After the user approves the preview, deploy to production (`vercel --prod` or the Vercel MCP production deploy), re-run the `/api/health` + Playwright checks against the production URL, and hand the user the final URL + password.

- [ ] **Step 9: Commit**

```bash
git add vercel.json requirements.txt .vercelignore README.md
git commit -m "feat(web): Vercel config, requirements, and docs for the web app"
```

---

## Self-Review

**Spec coverage:**
- Browser front end, zero install → Tasks 5 + 6 (static `public/` on Vercel). ✓
- Reuse engine unchanged → Tasks 3/4 import the engine; only Task 1 touches it (env key). ✓
- AI "just works", server key → Task 1 (env key) + Task 6 (`ANTHROPIC_API_KEY` in Vercel). ✓
- Private, shared password → Task 4 password gate + Task 6 `SLIDECHECK_PASSWORD`. ✓
- Privacy / ephemeral → Task 3 (TemporaryDirectory, nothing persisted) + Task 3 cwd-leak test. ✓
- Stateless self-contained response → Task 4 (base64 inline) + Task 5 (Blob downloads). ✓
- Validation / error handling (non-pptx 400, oversize 413, corrupt → per-file error, missing key → flag-only) → Tasks 3/4 + tests. ✓
- Serverless time-limit mitigation (cap + maxDuration) → Task 2 (CappedDescriber) + Task 6 (`maxDuration`). ✓
- Testing (engine unchanged, service tests, api tests, Playwright e2e) → Tasks 1–6. ✓
- Custom domain / rollout → Task 6 (preview → prod, optional subdomain in README/handoff). ✓
- Desktop GUI/CLI untouched → Global Constraints + Task 4 Step 7 full-suite run. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; commands have expected output. The only non-code "judgment" steps are the Playwright e2e (Task 5 Step 5, Task 6 Step 6) and the doc-verification (Task 6 Step 4), which are inherently interactive verification, with explicit assertions listed. ✓

**Type consistency:** `FileOutput`/`WebResult` fields defined in Task 3 are exactly the fields read in Task 4's payload (`filename`, `error`, `summary`, `report_html`, `fixed_filename`, `fixed_bytes` → `fixed_pptx_b64`). `summary` keys (`error`/`warning`/`info`/`auto_fixed`/`manual`) come from the existing `summary_counts` and are the keys Task 5 reads. `CappedDescriber(inner, max_images)` signature matches its use in Task 4. The header name `x-slidecheck-password` matches across Tasks 4 and 5. ✓
