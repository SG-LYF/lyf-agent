import json
import mimetypes
import re
import tempfile
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from google_auth_oauthlib.flow import Flow

from .config import (
    BASE_DIR, APP_BASE_URL, SESSION_SECRET, GOOGLE_CLIENT_SECRETS_FILE
)
from .drive import (
    SCOPES, save_credentials, get_service, ensure_category_tree, upload_file, search_drive
)
from .extract import extract_text
from .ai import classify, transcribe_if_audio
from .db import init_db, save_document, search_documents

app = FastAPI(title="AI Drive Manager Agent V1")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")

@app.get("/api/status")
def status():
    try:
        get_service()
        google_connected = True
    except Exception:
        google_connected = False
    return {
        "ok": True,
        "google_connected": google_connected,
        "ai_enabled": bool(__import__("app.config", fromlist=["OPENAI_API_KEY"]).OPENAI_API_KEY),
    }

@app.get("/api/auth/google")
def google_auth(request: Request):
    path = Path(GOOGLE_CLIENT_SECRETS_FILE)
    if not path.exists():
        raise HTTPException(
            400,
            "找不到 client_secret.json。请先在 Google Cloud 创建 OAuth Web application 凭据并放到项目根目录。"
        )
    redirect_uri = f"{APP_BASE_URL}/api/auth/google/callback"
    flow = Flow.from_client_secrets_file(
        str(path),
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    request.session["oauth_state"] = state
    return RedirectResponse(authorization_url)

@app.get("/api/auth/google/callback")
def google_callback(request: Request):
    state = request.session.get("oauth_state")
    redirect_uri = f"{APP_BASE_URL}/api/auth/google/callback"
    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=redirect_uri
    )
    flow.fetch_token(authorization_response=str(request.url))
    save_credentials(flow.credentials)
    ensure_category_tree()
    return RedirectResponse("/?connected=1")

def safe_title(title: str, fallback: str):
    title = re.sub(r'[\\/:*?"<>|\n\r]+', "_", (title or "").strip())
    return title[:120] or fallback

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    try:
        get_service()
    except Exception:
        raise HTTPException(401, "请先连接 Google Drive")

    original_name = file.filename or "untitled"
    suffix = Path(original_name).suffix
    mime_type = file.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"

    with tempfile.TemporaryDirectory() as td:
        local = Path(td) / original_name
        local.write_bytes(await file.read())

        text = extract_text(local)
        transcript = transcribe_if_audio(local)
        if transcript:
            text = f"{text}\n[语音转写]\n{transcript}".strip()

        result = classify(local, original_name, mime_type, text)
        title = safe_title(result.get("title"), Path(original_name).stem)
        final_name = f"{title}{suffix.lower()}" if suffix else title
        category = result.get("category_path", "99_待确认")
        uploaded = upload_file(local, final_name, category, mime_type)

        save_document({
            "drive_file_id": uploaded["id"],
            "original_name": original_name,
            "final_name": uploaded["name"],
            "mime_type": mime_type,
            "category_path": category,
            "summary": result.get("summary", ""),
            "extracted_text": text,
            "keywords": ", ".join(result.get("keywords", [])),
            "confidence": result.get("confidence", 0),
            "web_view_link": uploaded.get("webViewLink", ""),
        })

        return {
            "ok": True,
            "original_name": original_name,
            "final_name": uploaded["name"],
            "category_path": category,
            "summary": result.get("summary", ""),
            "keywords": result.get("keywords", []),
            "confidence": result.get("confidence", 0),
            "drive_file_id": uploaded["id"],
            "web_view_link": uploaded.get("webViewLink", ""),
            "transcript": transcript[:2000] if transcript else "",
        }

@app.get("/api/search")
def search(q: str):
    q = q.strip()
    if not q:
        return {"ok": True, "results": []}

    local = search_documents(q, limit=20)
    try:
        drive = search_drive(q, limit=20)
    except Exception:
        drive = []

    merged = []
    seen = set()
    for item in local:
        seen.add(item["drive_file_id"])
        merged.append({
            "source": "catalog",
            "id": item["drive_file_id"],
            "name": item["final_name"],
            "category_path": item["category_path"],
            "summary": item["summary"],
            "keywords": item["keywords"],
            "web_view_link": item["web_view_link"],
            "confidence": item["confidence"],
        })
    for item in drive:
        if item["id"] not in seen:
            merged.append({
                "source": "drive",
                "id": item["id"],
                "name": item["name"],
                "category_path": "",
                "summary": "",
                "keywords": "",
                "web_view_link": item.get("webViewLink", ""),
                "confidence": None,
            })
    return {"ok": True, "results": merged[:30]}

@app.post("/api/setup-folders")
def setup_folders():
    try:
        mapping = ensure_category_tree()
        return {"ok": True, "folders": mapping}
    except Exception as e:
        raise HTTPException(400, str(e))
