"""
Base AI provider interface
"""

from abc import ABC, abstractmethod
from typing import Optional


class AIProvider(ABC):
    """Base class for AI providers"""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available and configured"""
        pass

    @abstractmethod
    def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate a response from the AI.
        
        Args:
            prompt: User prompt
            system_prompt: System context prompt
            
        Returns:
            AI-generated response
        """
        pass

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available models"""
        pass
