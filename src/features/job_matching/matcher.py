import re
from collections import Counter
from typing import List, Set


TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}")

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


class JobDescriptionMatcher:
    def match(self, resume_markdown: str, job_description: str) -> dict:
        resume_text = (resume_markdown or "").strip()
        jd_text = (job_description or "").strip()

        if not resume_text:
            return {
                "status": "insufficient_input",
                "message": "Generate a resume first to run job matching.",
                "match_score": None,
                "matched_keywords": [],
                "missing_keywords": [],
                "recommendations": ["Generate resume content before running JD matching."],
            }

        if not jd_text:
            return {
                "status": "missing_job_description",
                "message": "Add a target job description to compute role-specific matching.",
                "match_score": None,
                "matched_keywords": [],
                "missing_keywords": [],
                "recommendations": ["Paste a job description in the form to unlock keyword matching."],
            }

        jd_keywords = self._extract_keywords(jd_text, top_n=32)
        resume_keywords = set(self._extract_keywords(resume_text, top_n=140))

        jd_phrases = self._extract_phrases(jd_text)
        resume_phrases = set(self._extract_phrases(resume_text))

        if not jd_keywords:
            return {
                "status": "insufficient_input",
                "message": "Could not extract enough JD keywords for matching.",
                "match_score": None,
                "matched_keywords": [],
                "missing_keywords": [],
                "recommendations": ["Use a fuller JD that includes required skills and responsibilities."],
            }

        matched_keywords = [keyword for keyword in jd_keywords if keyword in resume_keywords]
        missing_keywords = [keyword for keyword in jd_keywords if keyword not in resume_keywords]

        keyword_ratio = len(matched_keywords) / len(jd_keywords)
        phrase_ratio = (
            len([phrase for phrase in jd_phrases if phrase in resume_phrases]) / len(jd_phrases)
            if jd_phrases
            else keyword_ratio
        )
        score = round(((keyword_ratio * 0.75) + (phrase_ratio * 0.25)) * 100)

        recommendations: List[str] = []
        if missing_keywords:
            recommendations.append(
                "Tailor summary/skills/experience with these missing keywords: "
                + ", ".join(missing_keywords[:10])
            )
        if score < 55:
            recommendations.append("Rewrite at least 2 experience bullets to mirror the JD responsibilities and stack.")
        if score >= 75:
            recommendations.append("Strong role alignment detected. Final step: customize project bullets for this JD.")

        if not recommendations:
            recommendations.append("Good keyword coverage. Keep wording natural and evidence-based.")

        return {
            "status": "ok",
            "message": "Job description matching complete.",
            "match_score": score,
            "matched_keywords": matched_keywords[:20],
            "missing_keywords": missing_keywords[:20],
            "recommendations": recommendations,
        }

    def _extract_phrases(self, text: str) -> List[str]:
        normalized_text = re.sub(r"\s+", " ", text.lower()).strip()
        return [phrase for phrase in PHRASE_KEYWORDS if phrase in normalized_text]

    def _extract_keywords(self, text: str, top_n: int) -> List[str]:
        normalized_text = re.sub(r"\s+", " ", text.lower()).strip()
        phrase_hits = self._extract_phrases(normalized_text)

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
