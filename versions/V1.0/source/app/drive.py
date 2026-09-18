import json
import mimetypes
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from .config import TOKEN_FILE, FOLDER_FILE, DRIVE_ROOT_FOLDER_NAME
from .categories import CATEGORY_TREE

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_MIME = "application/vnd.google-apps.folder"

def save_credentials(creds: Credentials):
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

def load_credentials():
    if not TOKEN_FILE.exists():
        return None
    try:
        return Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    except Exception:
        return None

def get_service():
    creds = load_credentials()
    if not creds:
        raise RuntimeError("Google Drive 尚未授权")
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def _escape(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")

def find_folder(service, name, parent_id=None):
    q = [
        f"name = '{_escape(name)}'",
        f"mimeType = '{FOLDER_MIME}'",
        "trashed = false",
    ]
    if parent_id:
        q.append(f"'{parent_id}' in parents")
    r = service.files().list(
        q=" and ".join(q),
        spaces="drive",
        fields="files(id,name,parents)",
        pageSize=20
    ).execute()
    return r.get("files", [None])[0] if r.get("files") else None

def ensure_folder(service, name, parent_id=None):
    found = find_folder(service, name, parent_id)
    if found:
        return found["id"]
    meta = {"name": name, "mimeType": FOLDER_MIME}
    if parent_id:
        meta["parents"] = [parent_id]
    f = service.files().create(body=meta, fields="id,name").execute()
    return f["id"]

def ensure_category_tree():
    service = get_service()
    root_id = ensure_folder(service, DRIVE_ROOT_FOLDER_NAME)
    mapping = {"": root_id}
    for parent, children in CATEGORY_TREE.items():
        parent_id = ensure_folder(service, parent, root_id)
        mapping[parent] = parent_id
        for child in children:
            child_id = ensure_folder(service, child, parent_id)
            mapping[f"{parent}/{child}"] = child_id
    FOLDER_FILE.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    return mapping

def folder_mapping():
    if FOLDER_FILE.exists():
        return json.loads(FOLDER_FILE.read_text(encoding="utf-8"))
    return ensure_category_tree()

def upload_file(local_path: Path, final_name: str, category_path: str, mime_type: str):
    service = get_service()
    mapping = folder_mapping()
    folder_id = mapping.get(category_path) or mapping.get("99_待确认")
    media = MediaFileUpload(str(local_path), mimetype=mime_type or "application/octet-stream", resumable=True)
    meta = {
        "name": final_name,
        "parents": [folder_id],
        "appProperties": {"ai_category": category_path}
    }
    f = service.files().create(
        body=meta,
        media_body=media,
        fields="id,name,mimeType,webViewLink,parents"
    ).execute()
    return f

def search_drive(query: str, limit=20):
    service = get_service()
    safe = _escape(query.strip())
    # Drive fullText 'contains' is token-based. Search both file name and indexed text.
    q = f"trashed = false and (name contains '{safe}' or fullText contains '{safe}')"
    r = service.files().list(
        q=q,
        spaces="drive",
        fields="files(id,name,mimeType,webViewLink,modifiedTime,parents)",
        orderBy="modifiedTime desc",
        pageSize=limit
    ).execute()
    return r.get("files", [])
