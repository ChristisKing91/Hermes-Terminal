"""
Ollama AI provider integration
"""

import httpx
import logging
from typing import Optional
from .base import AIProvider

logger = logging.getLogger(__name__)


class OllamaProvider(AIProvider):
    """Ollama local AI provider"""

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = 120.0

    def is_available(self) -> bool:
        """Check if Ollama is running and model is available"""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "").split(":")[0] for m in models]
                    model_base = self.model.split(":")[0]
                    return model_base in model_names
        except Exception as e:
            logger.debug(f"Ollama availability check failed: {e}")
        return False

    def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate response using Ollama"""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return f"Error: {str(e)}"

    def list_models(self) -> list[str]:
        """List available Ollama models"""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    return [m.get("name", "") for m in models]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
        return []
