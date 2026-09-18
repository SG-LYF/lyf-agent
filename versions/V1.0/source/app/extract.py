import base64
from pathlib import Path
from pypdf import PdfReader
from docx import Document

TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".webm", ".mp4", ".mpeg", ".mpga"}

def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXTENSIONS:
            return path.read_text(encoding="utf-8", errors="ignore")[:50000]
        if ext == ".pdf":
            reader = PdfReader(str(path))
            chunks = []
            for i, page in enumerate(reader.pages[:100], start=1):
                text = page.extract_text() or ""
                if text.strip():
                    chunks.append(f"\n[第{i}页]\n{text}")
            return "".join(chunks)[:50000]
        if ext == ".docx":
            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs)[:50000]
    except Exception:
        return ""
    return ""

def image_data_url(path: Path, mime_type: str) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{data}"
