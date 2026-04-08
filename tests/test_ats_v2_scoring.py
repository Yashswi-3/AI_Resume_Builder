import unittest

from src.domain.ats_models import ExperienceEntry, ProjectEntry, ResumeData
from src.features.ats.analyzer import ATSAnalyzer
from src.features.ats.jd_loader import get_role


class ATSV2ScoringTests(unittest.TestCase):
    def test_backend_profile_is_not_auto_rejected(self):
        role = get_role("backend_engineer")
        resume = ResumeData(
            skills=["Python", "RESTful API", "SQL", "Git", "Docker", "Redis", "Database Design"],
            experience=[
                ExperienceEntry(
                    title="Backend Engineer",
                    company="Acme",
                    duration="2021-2024",
                    location="Remote",
                    bullets=["Built microservices and reduced API latency by 30%"],
                )
            ],
            projects=[
                ProjectEntry(
                    name="Order Service",
                    technologies=["Python", "Kafka", "Redis"],
                    description="Designed REST API and caching layer",
                )
            ],
            raw_text=(
                "Professional Summary\n"
                "Backend engineer with 3 years of experience shipping APIs.\n"
                "Skills\nPython, RESTful API, SQL, Git, Docker, Redis, Database Design\n"
                "Experience\nBackend Engineer | Acme | 2021-2024 | Remote\n"
                "- Built microservices and reduced API latency by 30%\n"
                "Projects\nOrder Service | Python, Kafka, Redis | 2024\n"
                "- Designed REST API and caching layer\n"
                "test@example.com\nlinkedin.com/in/test"
            ),
            section_map={
                "summary": "Backend engineer with 3 years of experience shipping APIs.",
                "skills": "Python, RESTful API, SQL, Git, Docker, Redis, Database Design",
                "experience": "Backend Engineer | Acme | 2021-2024 | Remote\n- Built microservices and reduced API latency by 30%",
                "projects": "Order Service | Python, Kafka, Redis | 2024\n- Designed REST API and caching layer",
                "education": "",
            },
        )

        result = ATSAnalyzer().analyze_v2(resume, role)

        self.assertNotEqual(result.verdict, "reject")
        self.assertGreater(result.score, 0)

    def test_reject_when_core_signals_missing(self):
        role = get_role("backend_engineer")
        resume = ResumeData(
            skills=["MS Office"],
            experience=[],
            projects=[],
            raw_text="General profile with no backend experience",
            section_map={"summary": "", "skills": "MS Office", "experience": "", "projects": "", "education": ""},
        )

        result = ATSAnalyzer().analyze_v2(resume, role)

        self.assertEqual(result.verdict, "reject")
        self.assertEqual(result.score, 0)


if __name__ == "__main__":
    unittest.main()
