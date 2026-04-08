from __future__ import annotations

import json
import importlib
import re
from typing import Any

from src.domain.ats_models import OptimizedResume, ResumeData, RoleSpec
from src.prompts.ats_optimizer_prompt import build_ats_optimizer_prompt
from src.services.ai.gemini_client import GeminiClient

try:
    spacy = importlib.import_module("spacy")
except Exception:  # pragma: no cover
    spacy = None


class ResumeOptimizer:
    def __init__(self, gemini_client: GeminiClient):
        self._client = gemini_client
        self._nlp = self._load_nlp()

    def _load_nlp(self):
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

    def optimize(self, resume_data: ResumeData, role_spec: RoleSpec, keyword_gaps: list[str]) -> OptimizedResume:
        system_prompt, user_prompt = build_ats_optimizer_prompt(
            resume_data=resume_data,
            role_spec=role_spec,
            keyword_gaps=keyword_gaps,
        )
        raw_response = self._client.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            max_output_tokens=1800,
            response_mime_type="application/json",
        )
        payload = self._parse_json_response(raw_response)

        optimized = OptimizedResume(
            skills=str(payload.get("skills", "")).strip(),
            experience=str(payload.get("experience", "")).strip(),
            projects=str(payload.get("projects", "")).strip(),
            education=str(payload.get("education", "")).strip(),
            summary=str(payload.get("summary", "")).strip(),
        )

        hallucinated = self._find_outlier_noun_phrases(
            source_text=resume_data.raw_text,
            output_text="\n".join(optimized.to_dict().values()),
        )
        if len(hallucinated) > 80:
            raise RuntimeError(
                "Optimizer output contains potential fabricated terms: " + ", ".join(hallucinated[:8])
            )
        return optimized

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        candidate = (text or "").strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?", "", candidate).strip()
            candidate = re.sub(r"```$", "", candidate).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start >= 0 and end > start:
                return json.loads(candidate[start : end + 1])
            raise

    def _extract_noun_phrases(self, text: str) -> set[str]:
        clean = (text or "").strip().lower()
        if not clean:
            return set()

        if self._nlp is not None:
            doc = self._nlp(clean)
            if hasattr(doc, "noun_chunks"):
                try:
                    return {chunk.text.strip() for chunk in doc.noun_chunks if len(chunk.text.strip()) > 2}
                except Exception:
                    pass

        tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}", clean)
        return set(tokens)

    def _find_outlier_noun_phrases(self, source_text: str, output_text: str) -> list[str]:
        source_phrases = self._extract_noun_phrases(source_text)
        output_phrases = self._extract_noun_phrases(output_text)
        allowlist = {
            "resume",
            "summary",
            "skills",
            "experience",
            "projects",
            "education",
            "optimized",
            "impact",
            "led",
            "built",
            "improved",
            "designed",
            "developed",
        }
        outliers = [
            phrase
            for phrase in output_phrases
            if phrase not in source_phrases and phrase not in allowlist and len(phrase) > 3
        ]
        return sorted(outliers)
