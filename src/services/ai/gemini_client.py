from typing import Any, Dict, List
import time

import requests


class GeminiClient:
    DEFAULT_MODELS = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-001",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash-lite-001",
        "gemini-flash-latest",
        "gemini-pro-latest",
    ]

    API_TEMPLATES = [
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "https://generativelanguage.googleapis.com/v1/models/{model}:generateContent",
    ]

    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        api_key: str,
        model: str = "",
        timeout_seconds: int = 60,
        max_retries: int = 2,
    ):
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.session = requests.Session()
        self._last_request_attempts = 0
        self._last_call_details: Dict[str, Any] = {"status": "not_started"}

    def get_last_call_details(self) -> Dict[str, Any]:
        details = dict(self._last_call_details)
        if isinstance(details.get("errors"), list):
            details["errors"] = list(details["errors"])
        return details

    def _candidate_models(self) -> List[str]:
        models: List[str] = []
        if self.model:
            models.append(self.model)
        for model in self.DEFAULT_MODELS:
            if model not in models:
                models.append(model)
        return models

    @staticmethod
    def _extract_text(body: Dict[str, Any]) -> str:
        candidates = body.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(part.get("text", "") for part in parts).strip()

    @staticmethod
    def _extract_error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
            return payload.get("error", {}).get("message", response.text)
        except Exception:
            return response.text

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_output_tokens: int,
        response_mime_type: str = "",
    ) -> str:
        if not self.api_key:
            self._last_call_details = {
                "status": "error",
                "provider": "gemini",
                "error": "GEMINI_API_KEY is missing",
                "errors": ["missing_api_key"],
            }
            raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file.")

        combined_prompt = (
            f"System instruction:\n{system_prompt}\n\n"
            f"User request:\n{user_prompt}"
        )

        generation_config: Dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        }
        if response_mime_type:
            generation_config["responseMimeType"] = response_mime_type

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": combined_prompt}],
                }
            ],
            "generationConfig": generation_config,
        }

        errors: List[str] = []
        for model in self._candidate_models():
            for template in self.API_TEMPLATES:
                url = template.format(model=model)
                response = self._post_with_retry(url=url, payload=payload)
                attempts = self._last_request_attempts

                if response is None:
                    errors.append(f"{model}:request_failed")
                    self._last_call_details = {
                        "status": "error",
                        "provider": "gemini",
                        "model": model,
                        "endpoint": template,
                        "attempts": attempts,
                        "error": "request_failed",
                        "errors": list(errors),
                    }
                    continue

                if response.status_code == 404:
                    errors.append(f"{model}:404")
                    self._last_call_details = {
                        "status": "error",
                        "provider": "gemini",
                        "model": model,
                        "endpoint": template,
                        "attempts": attempts,
                        "error": "404_not_found",
                        "errors": list(errors),
                    }
                    continue

                if response.status_code >= 400:
                    message = self._extract_error_message(response)
                    errors.append(f"{model}:{response.status_code}:{message[:120]}")
                    self._last_call_details = {
                        "status": "error",
                        "provider": "gemini",
                        "model": model,
                        "endpoint": template,
                        "attempts": attempts,
                        "error": f"http_{response.status_code}",
                        "error_message": message[:240],
                        "errors": list(errors),
                    }
                    continue

                text = self._extract_text(response.json())
                if text:
                    self._last_call_details = {
                        "status": "success",
                        "provider": "gemini",
                        "model": model,
                        "endpoint": template,
                        "attempts": attempts,
                        "response_mime_type": response_mime_type or "text/plain",
                    }
                    return text

                errors.append(f"{model}:empty")
                self._last_call_details = {
                    "status": "error",
                    "provider": "gemini",
                    "model": model,
                    "endpoint": template,
                    "attempts": attempts,
                    "error": "empty_response",
                    "errors": list(errors),
                }

        self._last_call_details = {
            "status": "error",
            "provider": "gemini",
            "error": "no_compatible_model",
            "errors": list(errors),
        }

        raise RuntimeError(
            "No compatible Gemini model responded successfully. Tried: " + ", ".join(errors)
        )

    def _post_with_retry(self, url: str, payload: Dict[str, Any]) -> requests.Response | None:
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException:
                if attempt >= self.max_retries:
                    self._last_request_attempts = attempt + 1
                    return None
                time.sleep(0.6 * (attempt + 1))
                continue

            if response.status_code in self.RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                time.sleep(0.6 * (attempt + 1))
                continue

            self._last_request_attempts = attempt + 1
            return response

        self._last_request_attempts = self.max_retries + 1
        return None
