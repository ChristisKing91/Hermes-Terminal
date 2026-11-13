"""
Ollama AI provider integration
"""

import httpx
import logging
from typing import Optional
from .base import AIProvider

logger = logging.getLogger(__name__)

AI_TIMEOUT_MESSAGE = "The local model took too long to respond. Try again or use a smaller prompt."


class AITimeoutError(RuntimeError):
    """Raised when local model generation exceeds the configured timeout."""


class OllamaProvider(AIProvider):
    """Ollama local AI provider"""

    def __init__(
        self, base_url: str, model: str, timeout: float = 300.0, *, trust_env: bool = True
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.trust_env = trust_env

    def is_available(self) -> bool:
        """Check if Ollama is running and model is available"""
        try:
            with httpx.Client(timeout=5.0, trust_env=self.trust_env) as client:
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

            timeout = httpx.Timeout(self.timeout, connect=10.0)
            with httpx.Client(timeout=timeout, trust_env=self.trust_env) as client:
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
        except httpx.TimeoutException as e:
            logger.warning("Ollama generation timed out: %s", e)
            raise AITimeoutError(AI_TIMEOUT_MESSAGE) from e
        except (httpx.HTTPError, ValueError, KeyError) as e:
            logger.error(f"Ollama generation failed: {e}")
            return ""

    def embed(self, text: str) -> list[float]:
        """Generate one vector with the selected model without truncating the input."""
        try:
            timeout = httpx.Timeout(self.timeout, connect=10.0)
            with httpx.Client(timeout=timeout, trust_env=self.trust_env) as client:
                response = client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": text, "truncate": False},
                )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict) or data.get("model") != self.model:
                    return []
                vectors = data.get("embeddings")
                if isinstance(vectors, list) and len(vectors) == 1 and isinstance(vectors[0], list):
                    return vectors[0]
        except httpx.TimeoutException as error:
            raise AITimeoutError(AI_TIMEOUT_MESSAGE) from error
        except (httpx.HTTPError, ValueError):
            logger.warning("Ollama embedding request failed")
        return []

    def list_models(self) -> list[str]:
        """List available Ollama models"""
        try:
            with httpx.Client(timeout=5.0, trust_env=self.trust_env) as client:
                response = client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    return [m.get("name", "") for m in models]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
        return []
