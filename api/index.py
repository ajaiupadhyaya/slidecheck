"""SlideCheck web API — exposed to Vercel as a Python (ASGI) function.

On Vercel the platform serves the static front end in ``public/`` and routes
only ``/api/*`` to this function; the StaticFiles mount below is therefore inert
on Vercel and exists so a single ``uvicorn api.index:app`` serves everything in
local development.
"""
import base64
import hmac
import json
import os

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from pptx_a11y.settings import get_describer
from pptx_a11y.web.analyze_service import analyze_upload
from pptx_a11y.web.describers import CappedDescriber
from pptx_a11y.web.export_service import export_with_plan

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
    if not hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Wrong or missing password.")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/analyze")
async def analyze(request: Request, files: list[UploadFile]):
    _check_password(request)
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")
    limit = _max_upload_bytes()
    mb = limit // (1024 * 1024)
    describer = CappedDescriber(get_describer({}), _max_ai_images())
    results = []
    for f in files:
        name = f.filename or "upload.pptx"
        if not name.lower().endswith(".pptx"):
            raise HTTPException(status_code=400, detail=f"Not a PowerPoint (.pptx) file: {name}")
        data = await f.read()
        if len(data) > limit:
            raise HTTPException(status_code=413, detail=f"{name} is larger than the {mb} MB limit.")
        results.append(analyze_upload(name, data, describer))
    return JSONResponse({"files": results})


@app.post("/api/export")
async def export(request: Request, files: list[UploadFile], plan: str = Form(...)):
    _check_password(request)
    try:
        plan_data = json.loads(plan)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid fix plan.")
    if not isinstance(plan_data, list):
        raise HTTPException(status_code=400, detail="Invalid fix plan.")
    limit = _max_upload_bytes()
    mb = limit // (1024 * 1024)
    results = []
    for f in files:
        name = f.filename or "upload.pptx"
        if not name.lower().endswith(".pptx"):
            raise HTTPException(status_code=400, detail=f"Not a PowerPoint (.pptx) file: {name}")
        data = await f.read()
        if len(data) > limit:
            raise HTTPException(status_code=413, detail=f"{name} is larger than the {mb} MB limit.")
        result = export_with_plan(name, data, plan_data)
        fixed_bytes = result.pop("fixed_bytes", None)
        result["fixed_pptx_b64"] = (
            base64.b64encode(fixed_bytes).decode("ascii") if fixed_bytes else None
        )
        results.append(result)
    return JSONResponse({"files": results})


# Local dev / e2e only — registered last so the /api routes match first.
_PUBLIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
if os.path.isdir(_PUBLIC):
    app.mount("/", StaticFiles(directory=_PUBLIC, html=True), name="static")
