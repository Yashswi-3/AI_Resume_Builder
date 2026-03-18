import re
from collections import Counter
from typing import List, Set


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
