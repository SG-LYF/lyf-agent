import sqlite3
from datetime import datetime, timezone
from .config import DB_FILE

def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drive_file_id TEXT UNIQUE NOT NULL,
            original_name TEXT NOT NULL,
            final_name TEXT NOT NULL,
            mime_type TEXT,
            category_path TEXT,
            summary TEXT,
            extracted_text TEXT,
            keywords TEXT,
            confidence REAL DEFAULT 0,
            web_view_link TEXT,
            created_at TEXT NOT NULL
        )
        """)
        conn.commit()

def save_document(doc):
    with connect() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO documents
        (drive_file_id, original_name, final_name, mime_type, category_path,
         summary, extracted_text, keywords, confidence, web_view_link, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc["drive_file_id"], doc["original_name"], doc["final_name"],
            doc.get("mime_type"), doc.get("category_path"), doc.get("summary", ""),
            doc.get("extracted_text", ""), doc.get("keywords", ""),
            float(doc.get("confidence", 0)), doc.get("web_view_link", ""),
            datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()

def search_documents(query, limit=20):
    q = f"%{query}%"
    with connect() as conn:
        rows = conn.execute("""
        SELECT * FROM documents
        WHERE original_name LIKE ?
           OR final_name LIKE ?
           OR category_path LIKE ?
           OR summary LIKE ?
           OR extracted_text LIKE ?
           OR keywords LIKE ?
        ORDER BY id DESC
        LIMIT ?
        """, (q, q, q, q, q, q, limit)).fetchall()
        return [dict(r) for r in rows]
