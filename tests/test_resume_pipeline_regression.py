import unittest

from src.services.resume.generator import ResumeGenerator
from src.ui.forms import _parse_experience


class _FakeGeminiClient:
    def generate_text(self, **kwargs):
        return '{"items": []}'

    def get_last_call_details(self):
        return {}


class ResumePipelineRegressionTests(unittest.TestCase):
    def test_experience_location_does_not_capture_sentence_fragment(self):
        raw_text = (
            "Founder\'s Office Intern Bangalore, In-Office | Skillcase | June 2025 – Jan 2026 | "
            "Createdandshared17+postsontheSkillcaseInstagramaccount. UsedHeyGen, ElevenLabs, andCanvaforproduction.\n"
            "- Handled operations of 6+ academic batches, from coordinating and scheduling between students and teachers.\n"
            "- Owned end-to-end product management for the Skillcase website and Android application.\n"
        )

        items = _parse_experience(raw_text)
        self.assertGreaterEqual(len(items), 1)
        self.assertEqual(items[0].location, "")

    def test_generator_keeps_deterministic_experience_headers(self):
        generator = ResumeGenerator(gemini_client=_FakeGeminiClient())

        primary = {
            "role": "Vice Chairperson Greater",
            "company": "IEEE WIE, Bennett University",
            "duration": "Jan 2024 - Jul 2024",
            "location": "Vice Chairperson Greater Noida",
            "highlights": [
                "Planned and executed 5+ university-level events involving 200+ participants.",
            ],
        }
        fallback = {
            "role": "Vice Chairperson",
            "company": "IEEE WIE, Bennett University",
            "duration": "Jan 2024 - Jul 2024",
            "location": "Greater Noida, Uttar Pradesh",
            "highlights": [
                "Coordinated multiple teams across logistics and scheduling.",
            ],
        }

        merged = generator._merge_experience_entries(primary, fallback)

        self.assertEqual(merged.get("role"), "Vice Chairperson")
        self.assertEqual(merged.get("location"), "Greater Noida, Uttar Pradesh")

    def test_generator_keeps_deterministic_project_headers(self):
        generator = ResumeGenerator(gemini_client=_FakeGeminiClient())

        primary = {
            "name": "Player Re-Identification in",
            "technologies": "Python, PyTorch",
            "year": "2025",
            "highlights": ["Built a tracker."],
        }
        fallback = {
            "name": "Player Re-Identification in Sports Footage",
            "technologies": "Python, PyTorch, YOLOv11, ResNet18, OpenCV",
            "year": "2025",
            "highlights": ["Built real-time tracking with stable identity assignment."],
        }

        merged = generator._merge_project_entries(primary, fallback)

        self.assertEqual(merged.get("name"), "Player Re-Identification in Sports Footage")
        self.assertEqual(merged.get("technologies"), "Python, PyTorch, YOLOv11, ResNet18, OpenCV")


if __name__ == "__main__":
    unittest.main()
