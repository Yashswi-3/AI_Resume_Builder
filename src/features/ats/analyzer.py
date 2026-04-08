import re
from collections import Counter
from math import ceil
from typing import List, Set

from src.domain.ats_models import RoleSpec, ScoreBreakdown, ScoreResult
from src.domain.ats_models import ResumeData
from src.features.ats.scorer import experience_score, format_score, keyword_score, project_score


TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}")
QUANT_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|x|k|m|million|billion|years?|months?)\b")

PHRASE_KEYWORDS = [
    "software engineer",
    "backend development",
    "distributed systems",
    "machine learning",
    "deep learning",
    "rest api",
    "api design",
    "scalable systems",
    "cross-functional",
]

EXPECTED_SECTIONS = [
    "professional summary",
    "skills",
    "education",
    "work experience",
    "projects",
]

ACTION_VERBS: Set[str] = {
    "achieved",
    "automated",
    "built",
    "collaborated",
    "created",
    "deployed",
    "delivered",
    "designed",
    "developed",
    "drove",
    "enhanced",
    "engineered",
    "implemented",
    "improved",
    "increased",
    "integrated",
    "launched",
    "led",
    "optimized",
    "predicted",
    "processed",
    "reduced",
    "shipped",
    "streamlined",
    "trained",
}

STOPWORDS: Set[str] = {
    "and",
    "are",
    "able",
    "all",
    "also",
    "any",
    "for",
    "from",
    "have",
    "into",
    "its",
    "more",
    "most",
    "that",
    "the",
    "their",
    "this",
    "those",
    "through",
    "using",
    "use",
    "with",
    "your",
    "you",
    "our",
    "was",
    "were",
    "has",
    "had",
    "will",
    "can",
    "should",
    "not",
}

GENERIC_JD_WORDS: Set[str] = {
    "candidate",
    "candidates",
    "deliver",
    "delivering",
    "experience",
    "experienced",
    "looking",
    "reliable",
    "responsibility",
    "responsibilities",
    "role",
    "solution",
    "solutions",
    "team",
    "teams",
    "work",
    "working",
}


class ATSAnalyzer:
    def analyze(self, resume_markdown: str, job_description: str = "") -> dict:
        resume_text = (resume_markdown or "").strip()
        if not resume_text:
            return {
                "status": "insufficient_input",
                "message": "Generate a resume first to compute ATS score.",
                "score": None,
                "recommendations": ["Generate resume content, then run ATS analysis."],
            }

        resume_lower = resume_text.lower()
        section_score = self._section_score(resume_lower)
        action_score = self._action_score(resume_text)
        quantification_score = self._quantification_score(resume_lower)

        jd_keywords = self._extract_keywords(job_description, top_n=35)
        resume_keywords = set(self._extract_keywords(resume_text, top_n=100))
        matched_keywords = [keyword for keyword in jd_keywords if keyword in resume_keywords]

        if jd_keywords:
            keyword_score = round((len(matched_keywords) / len(jd_keywords)) * 100)
        else:
            keyword_score = 75

        score = round(
            (section_score * 0.35)
            + (action_score * 0.25)
            + (quantification_score * 0.20)
            + (keyword_score * 0.20)
        )

        recommendations = self._recommendations(
            section_score=section_score,
            action_score=action_score,
            quantification_score=quantification_score,
            keyword_score=keyword_score,
            jd_keywords=jd_keywords,
            matched_keywords=matched_keywords,
        )

        return {
            "status": "ok",
            "message": "ATS analysis complete.",
            "score": score,
            "recommendations": recommendations,
            "diagnostics": {
                "section_score": section_score,
                "action_verb_score": action_score,
                "quantification_score": quantification_score,
                "keyword_score": keyword_score,
                "matched_keywords": matched_keywords[:15],
                "total_jd_keywords": len(jd_keywords),
            },
        }

    def _section_score(self, resume_lower: str) -> int:
        hits = 0
        for section in EXPECTED_SECTIONS:
            if f"## {section}" in resume_lower:
                hits += 1
        return round((hits / len(EXPECTED_SECTIONS)) * 100)

    def _action_score(self, resume_text: str) -> int:
        bullet_lines: List[str] = []
        for line in resume_text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("- "):
                continue

            bullet = stripped[2:].strip().lower()
            # Skip role/project header lines that are represented as bullets with pipes.
            if " | " in bullet and len([part for part in bullet.split("|") if part.strip()]) >= 3:
                continue

            if bullet:
                bullet_lines.append(bullet)

        if not bullet_lines:
            return 0

        strong = 0
        for bullet in bullet_lines:
            first_word = bullet.split(" ", 1)[0].strip(".,:;!?()[]{}") if bullet else ""
            if first_word in ACTION_VERBS:
                strong += 1

        return round((strong / len(bullet_lines)) * 100)

    def _quantification_score(self, resume_lower: str) -> int:
        hits = len(QUANT_PATTERN.findall(resume_lower))
        return min(100, hits * 18)

    def _extract_keywords(self, text: str, top_n: int) -> List[str]:
        if not text:
            return []

        normalized_text = re.sub(r"\s+", " ", text.lower()).strip()

        phrase_hits: List[str] = []
        for phrase in PHRASE_KEYWORDS:
            if phrase in normalized_text:
                phrase_hits.append(phrase)

        tokens = [self._normalize_token(token) for token in TOKEN_PATTERN.findall(normalized_text)]
        filtered = [
            token
            for token in tokens
            if token
            and token not in STOPWORDS
            and token not in GENERIC_JD_WORDS
            and len(token) >= 3
        ]

        counts = Counter(filtered)
        ordered: List[str] = list(dict.fromkeys(phrase_hits))
        for keyword, _ in counts.most_common(top_n * 2):
            if keyword not in ordered:
                ordered.append(keyword)
            if len(ordered) >= top_n:
                break

        return ordered[:top_n]

    def _normalize_token(self, token: str) -> str:
        value = token.strip().lower().strip(".,:;!?()[]{}")
        replacements = {
            "apis": "api",
            "systems": "system",
            "engineers": "engineer",
            "teams": "team",
            "collaborated": "collaboration",
            "collaborate": "collaboration",
            "collaborating": "collaboration",
            "designed": "design",
            "designing": "design",
            "developed": "develop",
            "developing": "develop",
            "implemented": "implement",
            "implementing": "implement",
            "optimized": "optimize",
            "optimizing": "optimize",
        }
        return replacements.get(value, value)

    def _recommendations(
        self,
        section_score: int,
        action_score: int,
        quantification_score: int,
        keyword_score: int,
        jd_keywords: List[str],
        matched_keywords: List[str],
    ) -> List[str]:
        recommendations: List[str] = []

        if section_score < 100:
            recommendations.append("Ensure all core sections are present: Summary, Skills, Education, Work Experience, Projects.")
        if action_score < 60:
            recommendations.append("Start more bullets with strong action verbs like 'Built', 'Implemented', or 'Optimized'.")
        if quantification_score < 45:
            recommendations.append("Add measurable impact (%, counts, time saved, latency reduction, throughput gains).")
        if jd_keywords and keyword_score < 65:
            missing = [keyword for keyword in jd_keywords if keyword not in matched_keywords][:8]
            if missing:
                recommendations.append("Improve JD alignment by incorporating keywords: " + ", ".join(missing))

        if not recommendations:
            recommendations.append("ATS profile looks strong. Focus next on tailoring bullets to each application.")

        return recommendations

    def analyze_v2(self, resume_data: ResumeData, role_spec: RoleSpec) -> ScoreResult:
        if not resume_data.raw_text.strip():
            return ScoreResult(
                score=0,
                verdict="reject",
                breakdown=ScoreBreakdown(),
                keyword_gaps=[],
                weak_sections={"summary": "Resume text is empty."},
                recruiter_adjustments={},
                reason="No resume content to analyze.",
            )

        normalized_synonyms = self._normalize_synonyms(role_spec.synonyms)
        skill_candidates = self._build_skill_candidates(resume_data=resume_data, role_spec=role_spec)
        resume_lower = (resume_data.raw_text or "").lower()

        required_matches = [
            item
            for item in role_spec.required
            if self._keyword_present(
                keyword=item,
                skill_candidates=skill_candidates,
                resume_lower=resume_lower,
                synonym_map=normalized_synonyms,
            )
        ]
        minimum_required = 0
        if role_spec.required:
            minimum_required = max(1, ceil(len(role_spec.required) * 0.5))

        years_detected = self._estimate_experience_years(resume_data)

        if len(required_matches) < minimum_required or years_detected < role_spec.experience_threshold_years:
            reason_bits = []
            if len(required_matches) < minimum_required:
                reason_bits.append(
                    f"Required skills below threshold ({len(required_matches)}/{max(1, len(role_spec.required))})"
                )
            if years_detected < role_spec.experience_threshold_years:
                reason_bits.append(
                    f"Experience threshold not met ({years_detected}/{role_spec.experience_threshold_years} years)"
                )
            return ScoreResult(
                score=0,
                verdict="reject",
                breakdown=ScoreBreakdown(),
                keyword_gaps=role_spec.high_impact_keywords[:12],
                weak_sections={
                    "skills": "Add role-required skills only where evidence exists in your history.",
                    "experience": "Show stronger experience context with quantified scope.",
                },
                recruiter_adjustments={},
                reason="; ".join(reason_bits),
            )

        skill_component = keyword_score(
            resume_skills=skill_candidates,
            role_required=role_spec.required,
            role_preferred=role_spec.preferred,
            synonyms=normalized_synonyms,
        )
        experience_component = experience_score(resume_data.experience, role_spec.seniority_keywords)
        project_component = project_score(resume_data.projects, role_spec.preferred)
        format_component = format_score(resume_data.raw_text)

        breakdown = ScoreBreakdown(
            skills_match=skill_component,
            experience_relevance=experience_component,
            project_alignment=project_component,
            format_quality=format_component,
        )

        weights = role_spec.section_weights or {
            "skills_match": 0.4,
            "experience_relevance": 0.3,
            "project_alignment": 0.2,
            "format_quality": 0.1,
        }
        weighted = (
            (skill_component * weights.get("skills_match", 0.4))
            + (experience_component * weights.get("experience_relevance", 0.3))
            + (project_component * weights.get("project_alignment", 0.2))
            + (format_component * weights.get("format_quality", 0.1))
        ) * 100

        adjustments = self._apply_recruiter_simulation(resume_data)
        score = int(max(0, min(100, round(weighted + adjustments["total"]))))

        if score < 50:
            verdict = "reject"
        elif score < 75:
            verdict = "borderline"
        else:
            verdict = "strong"

        keyword_gaps = [
            item
            for item in role_spec.high_impact_keywords
            if not self._keyword_present(
                keyword=item,
                skill_candidates=skill_candidates,
                resume_lower=resume_lower,
                synonym_map=normalized_synonyms,
            )
        ]
        weak_sections = self._weak_section_suggestions(breakdown)

        return ScoreResult(
            score=score,
            verdict=verdict,
            breakdown=breakdown,
            keyword_gaps=keyword_gaps[:15],
            weak_sections=weak_sections,
            recruiter_adjustments=adjustments,
            reason="ATS scoring completed",
        )

    def _apply_recruiter_simulation(self, resume_data: ResumeData) -> dict[str, int]:
        text = resume_data.raw_text or ""
        lowered = text.lower()
        total = 0
        details: dict[str, int] = {}

        quantified_bullets = len(re.findall(r"\b\d+(?:\.\d+)?\s*(?:%|x|k|m|years?|months?)\b", lowered))
        if quantified_bullets >= 3:
            details["quantified_achievements"] = 6
            total += 6
        elif quantified_bullets == 0:
            details["no_quantification"] = -6
            total -= 6

        bullets = [line.strip().lower() for line in text.splitlines() if line.strip().startswith("-")]
        unique_bullets = len(set(bullets))
        if bullets and unique_bullets < len(bullets):
            details["repeated_bullets"] = -4
            total -= 4

        action_verb_hits = len(
            [
                line
                for line in bullets
                if re.match(r"^-\s*(built|led|reduced|increased|designed|implemented|optimized)\b", line)
            ]
        )
        if action_verb_hits >= 3:
            details["impact_verbs"] = 3
            total += 3

        has_email = bool(re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text))
        has_linkedin = "linkedin" in lowered
        if not (has_email or has_linkedin):
            details["missing_contact_info"] = -3
            total -= 3

        token_count = max(1, len(re.findall(r"\w+", lowered)))
        skill_density = len(resume_data.skills) / token_count
        if skill_density > 0.04:
            details["buzzword_stuffing"] = -5
            total -= 5

        details["total"] = total
        return details

    def _weak_section_suggestions(self, breakdown: ScoreBreakdown) -> dict[str, str]:
        suggestions: dict[str, str] = {}
        if breakdown.skills_match < 0.65:
            suggestions["skills"] = "Prioritize exact role vocabulary and canonical tooling names in Skills."
        if breakdown.experience_relevance < 0.65:
            suggestions["experience"] = "Rewrite bullets to emphasize scope, ownership, and quantifiable outcomes."
        if breakdown.project_alignment < 0.65:
            suggestions["projects"] = "Surface projects that map directly to the role stack and impact keywords."
        if breakdown.format_quality < 0.65:
            suggestions["format"] = "Use clear section headers and ATS-friendly bullet formatting."
        return suggestions

    def _normalize_synonyms(self, synonyms: dict[str, list[str]]) -> dict[str, list[str]]:
        normalized: dict[str, list[str]] = {}
        for key, values in (synonyms or {}).items():
            canonical = (key or "").strip().lower()
            if not canonical:
                continue
            normalized[canonical] = [
                value.strip().lower()
                for value in values
                if isinstance(value, str) and value.strip()
            ]
        return normalized

    def _build_skill_candidates(self, resume_data: ResumeData, role_spec: RoleSpec) -> list[str]:
        candidates = [item.strip() for item in resume_data.skills if item.strip()]
        raw_lower = (resume_data.raw_text or "").lower()

        # Add role and synonym terms present in free text so missing section headers do not zero out scoring.
        terms: set[str] = set(role_spec.required + role_spec.preferred + role_spec.high_impact_keywords)
        for key, aliases in (role_spec.synonyms or {}).items():
            if key:
                terms.add(key)
            terms.update(aliases)

        for term in terms:
            normalized = (term or "").strip()
            if normalized and normalized.lower() in raw_lower:
                candidates.append(normalized)

        deduped: list[str] = []
        seen: set[str] = set()
        for value in candidates:
            normalized = value.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(value)
        return deduped

    def _keyword_present(
        self,
        keyword: str,
        skill_candidates: list[str],
        resume_lower: str,
        synonym_map: dict[str, list[str]],
    ) -> bool:
        target = (keyword or "").strip().lower()
        if not target:
            return False

        skill_values = [value.lower() for value in skill_candidates]
        for skill in skill_values:
            if target == skill or target in skill or skill in target:
                return True

        if target in resume_lower:
            return True

        for alias in synonym_map.get(target, []):
            if not alias:
                continue
            if alias in resume_lower:
                return True
            for skill in skill_values:
                if alias == skill or alias in skill or skill in alias:
                    return True
        return False

    def _estimate_experience_years(self, resume_data: ResumeData) -> int:
        raw_text = resume_data.raw_text or ""
        explicit_year_mentions = [
            int(match.group(1))
            for match in re.finditer(r"(\d+)\+?\s*years?", raw_text, flags=re.IGNORECASE)
        ]
        explicit_max = max(explicit_year_mentions) if explicit_year_mentions else 0

        derived_max = 0
        for entry in resume_data.experience:
            duration = (entry.duration or "").strip()
            if not duration:
                continue

            duration_years = [
                int(match.group(1))
                for match in re.finditer(r"(\d+)\+?\s*years?", duration, flags=re.IGNORECASE)
            ]
            if duration_years:
                derived_max = max(derived_max, max(duration_years))

            year_tokens = [int(token) for token in re.findall(r"\b(19\d{2}|20\d{2})\b", duration)]
            if len(year_tokens) >= 2:
                start_year = min(year_tokens)
                end_year = max(year_tokens)
                if 0 <= (end_year - start_year) <= 40:
                    derived_max = max(derived_max, end_year - start_year)

        return max(explicit_max, derived_max)
