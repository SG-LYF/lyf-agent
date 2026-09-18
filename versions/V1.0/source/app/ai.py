import json
import re
from pathlib import Path
from typing import Optional
from openai import OpenAI
from .config import OPENAI_API_KEY, OPENAI_MODEL
from .categories import ALLOWED_CATEGORY_PATHS
from .extract import IMAGE_EXTENSIONS, AUDIO_EXTENSIONS, image_data_url

def _client():
    if not OPENAI_API_KEY:
        return None
    return OpenAI(api_key=OPENAI_API_KEY)

def transcribe_if_audio(path: Path) -> str:
    if path.suffix.lower() not in AUDIO_EXTENSIONS:
        return ""
    client = _client()
    if not client:
        return ""
    try:
        with open(path, "rb") as f:
            r = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=f
            )
        return getattr(r, "text", "") or ""
    except Exception:
        return ""

def _fallback(original_name: str, mime_type: str, extracted_text: str):
    hay = f"{original_name} {extracted_text}".lower()
    rules = [
        (["mom", "ministry of manpower", "loc", "work pass"], "03_政府与证件/MOM"),
        (["acra", "bizfile", "business profile"], "03_政府与证件/ACRA"),
        (["corppass"], "03_政府与证件/Corppass"),
        (["iras", "tax", "income tax"], "02_财务税务/IRAS"),
        (["ocbc", "dbs", "bank", "paynow"], "02_财务税务/银行"),
        (["invoice", "receipt", "发票"], "02_财务税务/发票"),
        (["shopee"], "01_公司业务/Shopee"),
        (["easyboss"], "01_公司业务/EasyBoss"),
        (["supplier", "供应商"], "01_公司业务/供应商"),
        (["contract", "agreement", "合同"], "01_公司业务/合同"),
        (["flight", "hotel", "trip", "travel", "航班", "酒店"], "04_家庭个人/旅行"),
        (["insurance", "policy", "保险"], "04_家庭个人/保险"),
        (["school", "education", "aeis", "课程", "学校"], "04_家庭个人/教育"),
    ]
    for keys, category in rules:
        if any(k in hay for k in keys):
            return {
                "category_path": category,
                "title": Path(original_name).stem,
                "summary": "按关键词规则自动归档。",
                "keywords": [k for k in keys if k in hay][:6],
                "confidence": 0.72,
            }
    if mime_type.startswith("image/"):
        category = "05_图片与扫描件"
    elif mime_type.startswith("audio/") or mime_type.startswith("video/"):
        category = "06_语音与会议记录"
    else:
        category = "99_待确认"
    return {
        "category_path": category,
        "title": Path(original_name).stem,
        "summary": "未启用AI或AI未能可靠判断，已按基础规则归档。",
        "keywords": [],
        "confidence": 0.40,
    }

def classify(path: Path, original_name: str, mime_type: str, extracted_text: str):
    client = _client()
    if not client:
        return _fallback(original_name, mime_type, extracted_text)

    categories = "\n".join(f"- {x}" for x in ALLOWED_CATEGORY_PATHS)
    prompt = f"""
你是企业资料归档助手。请分析文件并返回严格JSON，不要markdown。
只能从以下分类中选择 category_path：
{categories}

返回字段：
category_path: string
title: 简洁中文或英文标题，不要扩展名
summary: 1-3句摘要
keywords: 最多8个字符串
confidence: 0到1

规则：
1. 不确定时选择 99_待确认。
2. 不要把所有图片都放进图片文件夹；如果图片内容明显是银行、MOM、Shopee等，应按内容分类。
3. title适合当文件名，避免 / \\ : * ? " < > | 等非法字符。
4. 不编造未见内容。

文件名：{original_name}
MIME：{mime_type}
已提取文字：
{extracted_text[:18000]}
"""
    try:
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            response = client.responses.create(
                model=OPENAI_MODEL,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": image_data_url(path, mime_type or "image/jpeg")}
                    ]
                }]
            )
        else:
            response = client.responses.create(model=OPENAI_MODEL, input=prompt)

        text = response.output_text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
        data = json.loads(text)
        if data.get("category_path") not in ALLOWED_CATEGORY_PATHS:
            data["category_path"] = "99_待确认"
            data["confidence"] = min(float(data.get("confidence", 0)), 0.5)
        data["confidence"] = max(0.0, min(1.0, float(data.get("confidence", 0))))
        data["keywords"] = data.get("keywords") or []
        return data
    except Exception:
        return _fallback(original_name, mime_type, extracted_text)
