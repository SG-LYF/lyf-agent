
import mimetypes, re, tempfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from google_auth_oauthlib.flow import Flow
from .config import BASE_DIR, APP_BASE_URL, SESSION_SECRET, GOOGLE_CLIENT_SECRETS_FILE, DRIVE_ROOT_FOLDER_NAME
from .drive import SCOPES, save_credentials, get_service, ensure_category_tree, upload_file, search_drive
from .extract import extract_text
from .ai import classify, transcribe_if_audio, test_ai_connection
from .db import init_db, save_document, smart_search_documents

app=FastAPI(title="AI Drive Manager Agent V1.4.2")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
app.mount("/static",StaticFiles(directory=str(BASE_DIR/"static")),name="static")

@app.on_event("startup")
def startup(): init_db()

@app.get("/")
def home(): return FileResponse(BASE_DIR/"static"/"index.html")

@app.get("/api/status")
def status():
    try: get_service(); g=True
    except Exception: g=False
    from .config import OPENAI_API_KEY, OPENAI_MODEL
    return {"ok":True,"version":"1.4.2","google_connected":g,"ai_configured":bool(OPENAI_API_KEY),"ai_model":OPENAI_MODEL}

@app.get("/api/test-ai")
def test_ai(): return test_ai_connection()

@app.get("/api/auth/google")
def google_auth(request:Request):
    redirect=f"{APP_BASE_URL}/api/auth/google/callback"
    flow=Flow.from_client_secrets_file(GOOGLE_CLIENT_SECRETS_FILE,scopes=SCOPES,redirect_uri=redirect)
    url,state=flow.authorization_url(access_type="offline",include_granted_scopes="true",prompt="consent")
    request.session["oauth_state"]=state
    return RedirectResponse(url)

@app.get("/api/auth/google/callback")
def google_callback(request:Request):
    redirect=f"{APP_BASE_URL}/api/auth/google/callback"
    flow=Flow.from_client_secrets_file(GOOGLE_CLIENT_SECRETS_FILE,scopes=SCOPES,state=request.session.get("oauth_state"),redirect_uri=redirect)
    flow.fetch_token(authorization_response=str(request.url))
    save_credentials(flow.credentials); ensure_category_tree()
    return RedirectResponse("/?connected=1")

def safe_title(s,fallback):
    s=re.sub(r'[\\/:*?"<>|\n\r]+',"_",(s or "").strip())
    return s[:120] or fallback

def save_idx(up,orig,mime,cat,summary,text,keywords,conf):
    save_document({"drive_file_id":up["id"],"original_name":orig,"final_name":up["name"],"mime_type":mime,
    "category_path":cat,"summary":summary,"extracted_text":text,"keywords":", ".join(keywords or []),
    "confidence":conf,"web_view_link":up.get("webViewLink","")})

@app.post("/api/upload")
async def upload(file:UploadFile=File(...)):
    try: get_service()
    except Exception: raise HTTPException(401,"请先连接 Google Drive")
    name=file.filename or "untitled"; suffix=Path(name).suffix
    mime=file.content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/name; p.write_bytes(await file.read())
        text=extract_text(p)
        transcript,terr=transcribe_if_audio(p)
        if transcript: text=f"{text}\n[语音转写]\n{transcript}".strip()
        result=classify(p,name,mime,text)
        title=safe_title(result.get("title"),Path(name).stem)
        cat=result.get("category_path","99_待确认")
        up=upload_file(p,f"{title}{suffix.lower()}" if suffix else title,cat,mime)
        save_idx(up,name,mime,cat,result.get("summary",""),text,result.get("keywords",[]),result.get("confidence",0))
        return {"ok":True,"final_name":up["name"],"category_path":cat,"summary":result.get("summary",""),
        "confidence":result.get("confidence",0),"web_view_link":up.get("webViewLink",""),"transcript":transcript or "",
        "ai_used":bool(result.get("ai_used")),"ai_error":result.get("ai_error",""),"transcript_error":terr or ""}

@app.post("/api/recording")
async def recording(file:UploadFile=File(...)):
    try: get_service()
    except Exception: raise HTTPException(401,"请先连接 Google Drive")
    name=file.filename or "voice_recording.webm"; mime=file.content_type or "audio/webm"
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/name; p.write_bytes(await file.read())
        transcript,terr=transcribe_if_audio(p)
        if not transcript: raise HTTPException(400,f"语音转写失败：{terr or '未获得文字'}")
        result=classify(p,name,mime,transcript)
        cat=result.get("category_path","06_语音与会议记录")
        title=safe_title(result.get("title"),"语音记录")
        summary=result.get("summary",""); keys=result.get("keywords",[]); conf=result.get("confidence",0)
        ext=Path(name).suffix.lower() or ".webm"
        audio_up=upload_file(p,f"{title}_原始语音{ext}",cat,mime)
        save_idx(audio_up,name,mime,cat,summary,transcript,keys,conf)
        md=Path(td)/f"{title}_转写文本.md"
        md.write_text(f"# {title}\n\n**分类：** {cat}\n\n**摘要：** {summary}\n\n## 语音转写\n\n{transcript}\n",encoding="utf-8")
        text_up=upload_file(md,md.name,cat,"text/markdown")
        save_idx(text_up,md.name,"text/markdown",cat,summary,transcript,keys,conf)
        return {"ok":True,"category_path":cat,"summary":summary,"confidence":conf,"transcript":transcript,
        "audio_link":audio_up.get("webViewLink",""),"text_link":text_up.get("webViewLink","")}

@app.get("/api/search")
def search(q:str):
    q=q.strip()
    if not q:return {"ok":True,"results":[]}
    local=smart_search_documents(q,20); drive=[]
    if not local:
        from .db import normalize_query
        dq=normalize_query(q)
        if dq:
            try: drive=search_drive(dq,20)
            except Exception: drive=[]
    merged=[]; seen=set()
    for x in local:
        seen.add(x["drive_file_id"])
        category=x.get("category_path") or ""
        full_path = DRIVE_ROOT_FOLDER_NAME + (f" / {category.replace('/', ' / ')}" if category else "")
        merged.append({"id":x["drive_file_id"],"name":x["final_name"],"category_path":category,"full_path":full_path,
        "mime_type":x.get("mime_type",""),"created_at":x.get("created_at",""),"summary":x.get("summary",""),
        "web_view_link":x.get("web_view_link",""),"search_score":x.get("search_score")})
    for x in drive:
        if x["id"] not in seen:
            merged.append({"id":x["id"],"name":x["name"],"category_path":"","full_path":DRIVE_ROOT_FOLDER_NAME,
            "mime_type":x.get("mimeType",""),"created_at":x.get("modifiedTime",""),"summary":"",
            "web_view_link":x.get("webViewLink",""),"search_score":None})
    return {"ok":True,"results":merged[:30]}

@app.post("/api/setup-folders")
def setup_folders():
    try:return {"ok":True,"folders":ensure_category_tree()}
    except Exception as e: raise HTTPException(400,str(e))
