from __future__ import annotations

import json
import importlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.domain.ats_models import RoleSpec

try:
    spacy = importlib.import_module("spacy")
except Exception:  # pragma: no cover
    spacy = None


@lru_cache(maxsize=1)
def _load_jd_map() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    path = root / "data" / "jd_skill_map.json"
    if not path.exists():
        return {"roles": {}}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_roles_map() -> dict[str, Any]:
    return _load_jd_map()


@lru_cache(maxsize=1)
def _spacy_nlp():
    if spacy is None:
        return None
    for model in ["en_core_web_sm", "en_core_web_md"]:
        try:
            return spacy.load(model)
        except Exception:
            continue
    try:
        return spacy.blank("en")
    except Exception:
        return None


def _normalize_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def get_role(role_id: str) -> RoleSpec:
    role_key = (role_id or "").strip()
    roles = get_roles_map().get("roles", {})
    if role_key not in roles:
        raise KeyError(f"Unknown role_id: {role_key}")

    payload = roles[role_key]
    weights = payload.get("section_weights") or {
        "skills_match": 0.4,
        "experience_relevance": 0.3,
        "project_alignment": 0.2,
        "format_quality": 0.1,
    }

    return RoleSpec(
        role_id=role_key,
        display_name=str(payload.get("display_name", role_key)).strip(),
        category=str(payload.get("category", "general")).strip(),
        required=_normalize_list(payload.get("required")),
        preferred=_normalize_list(payload.get("preferred")),
        seniority_keywords={
            str(level): _normalize_list(words)
            for level, words in (payload.get("seniority_keywords") or {}).items()
        },
        synonyms={
            str(term): _normalize_list(aliases)
            for term, aliases in (payload.get("synonyms") or {}).items()
        },
        experience_threshold_years=max(0, int(payload.get("experience_threshold_years", 0))),
        section_weights={
            "skills_match": float(weights.get("skills_match", 0.4)),
            "experience_relevance": float(weights.get("experience_relevance", 0.3)),
            "project_alignment": float(weights.get("project_alignment", 0.2)),
            "format_quality": float(weights.get("format_quality", 0.1)),
        },
        high_impact_keywords=_normalize_list(payload.get("high_impact_keywords")),
    )


def parse_jd_text(text: str) -> RoleSpec:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("jd_text is empty")

    required: list[str] = []
    preferred: list[str] = []

    nlp = _spacy_nlp()
    if nlp is not None:
        doc = nlp(raw)
        noun_chunks = []
        if hasattr(doc, "noun_chunks"):
            try:
                noun_chunks = [chunk.text.strip().lower() for chunk in doc.noun_chunks]
            except Exception:
                noun_chunks = []
        for chunk in noun_chunks:
            if len(chunk) < 3 or len(chunk.split()) > 5:
                continue
            if chunk not in required:
                required.append(chunk)

    tokens = [t.lower() for t in re.findall(r"[a-zA-Z][a-zA-Z0-9+.#-]{2,}", raw)]
    stopwords = {
        "and",
        "the",
        "for",
        "with",
        "you",
        "your",
        "our",
        "role",
        "team",
        "will",
        "are",
        "have",
    }
    freq: dict[str, int] = {}
    for token in tokens:
        if token in stopwords:
            continue
        freq[token] = freq.get(token, 0) + 1

    ranked = [key for key, _ in sorted(freq.items(), key=lambda item: item[1], reverse=True)]
    for keyword in ranked[:30]:
        if keyword not in required:
            preferred.append(keyword)

    required = required[:12] if required else ranked[:8]
    preferred = preferred[:20]

    return RoleSpec(
        role_id="custom_jd",
        display_name="Custom JD",
        category="custom",
        required=required,
        preferred=preferred,
        seniority_keywords={
            "junior": ["junior", "entry", "0-2"],
            "mid": ["mid", "3-5", "engineer"],
            "senior": ["senior", "lead", "staff", "principal", "architect"],
        },
        synonyms={},
        experience_threshold_years=0,
        section_weights={
            "skills_match": 0.4,
            "experience_relevance": 0.3,
            "project_alignment": 0.2,
            "format_quality": 0.1,
        },
        high_impact_keywords=ranked[:15],
    )
