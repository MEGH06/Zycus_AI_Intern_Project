import hashlib
import re


def clean_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text.strip())


def stable_hash(text: str, prefix: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{digest}"


def sentence_split(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in parts if s]


def extract_quote(text: str, keywords: list[str], max_chars: int = 180) -> str:
    lower = text.lower()
    best = -1
    for kw in keywords:
        pos = lower.find(kw.lower())
        if pos != -1 and (best == -1 or pos < best):
            best = pos
    start = max(0, best - 30) if best != -1 else 0
    return text[start : start + max_chars]
