"""
OpenAI-compatible API provider
"""

import httpx
import logging
from typing import Optional
from .base import AIProvider

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(AIProvider):
    """OpenAI-compatible API provider"""

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = 120.0

    def is_available(self) -> bool:
        """Check if API is accessible"""
        if not self.api_key or not self.model:
            return False
        try:
            with httpx.Client(timeout=5.0) as client:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                response = client.get(
                    f"{self.base_url}/models",
                    headers=headers,
                )
                return response.status_code == 200
        except Exception as e:
            logger.debug(f"OpenAI API availability check failed: {e}")
        return False

    def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate response using OpenAI API"""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.7,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            return f"Error: {str(e)}"

    def list_models(self) -> list[str]:
        """List available models"""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    f"{self.base_url}/models",
                    headers=headers,
                )
                if response.status_code == 200:
                    data = response.json()
                    return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
        return []
