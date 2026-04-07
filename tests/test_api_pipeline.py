import time
import unittest

from fastapi.testclient import TestClient

from src.api.main import app


class ApiPipelineTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _auth_headers(self):
        unique_email = f"api_test_{int(time.time() * 1000)}@example.com"
        password = "StrongPass123"
        response = self.client.post(
            "/api/v1/auth/register",
            json={"email": unique_email, "password": password},
        )
        self.assertEqual(response.status_code, 201)
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_create_job_and_poll_status(self):
        headers = self._auth_headers()

        payload = {
            "resume_input": {
                "personal_info": {
                    "full_name": "test",
                    "email": "test",
                    "phone": "test",
                    "linkedin": "",
                    "github": "",
                    "portfolio": "",
                    "location": "test",
                },
                "career_summary": "test",
                "target_role": "test",
                "target_company": "test",
                "job_description": "test",
                "tone": "professional",
                "skills": ["test"],
                "education": [
                    {
                        "degree": "test",
                        "institution": "test",
                        "duration": "test",
                        "location": "test",
                        "details": "test",
                    }
                ],
                "experiences": [
                    {
                        "role": "test",
                        "company": "test",
                        "duration": "test",
                        "location": "test",
                        "bullet_points": ["test"],
                    }
                ],
                "projects": [
                    {
                        "name": "test",
                        "technologies": "test",
                        "year": "test",
                        "bullet_points": ["test"],
                    }
                ],
                "certifications": ["test"],
                "achievements": ["test"],
            },
            "template_key": "classic",
        }

        queued = self.client.post("/api/v1/resumes/jobs", headers=headers, json=payload)
        self.assertEqual(queued.status_code, 202)
        job_id = queued.json()["job_id"]

        final = None
        for _ in range(40):
            status = self.client.get(f"/api/v1/resumes/jobs/{job_id}", headers=headers)
            self.assertEqual(status.status_code, 200)
            body = status.json()
            final = body.get("status")
            if final in {"completed", "failed"}:
                break
            time.sleep(0.25)

        self.assertEqual(final, "completed")
        self.assertTrue(self.client.get(f"/api/v1/resumes/jobs/{job_id}", headers=headers).json().get("result_payload"))


if __name__ == "__main__":
    unittest.main()
