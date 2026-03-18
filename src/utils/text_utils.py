import re
import unicodedata
from typing import List

NON_ASCII_PATTERN = re.compile(r"[^\x00-\x7F]+")

TEXT_REPLACEMENTS = {
    "–": "-",
    "—": "-",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "•": "-",
    "◦": "-",
    "▪": "-",
    "\\": "",
}


def split_csv_or_lines(value: str) -> List[str]:
    if not value:
        return []
    normalized = value.replace("\n", ",")
    raw_items = [item.strip() for item in normalized.split(",") if item.strip()]

    cleaned: List[str] = []
    seen = set()
    skip_tokens = {"skill", "skills"}

    for item in raw_items:
        key = item.strip().lower()
        if key in skip_tokens:
            continue
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)

    return cleaned


def split_lines(value: str) -> List[str]:
    if not value:
        return []
    return [line.strip() for line in value.splitlines() if line.strip()]


def split_blocks(value: str) -> List[str]:
    if not value:
        return []
    blocks = re.split(r"\n\s*\n", value.strip())
    return [block.strip() for block in blocks if block.strip()]


def clean_text_for_pdf(text: str) -> str:
    if not text:
        return ""

    cleaned = text
    for source, target in TEXT_REPLACEMENTS.items():
        cleaned = cleaned.replace(source, target)

    cleaned = NON_ASCII_PATTERN.sub("", cleaned)
    return unicodedata.normalize("NFKD", cleaned).encode("latin-1", "ignore").decode("latin-1")
