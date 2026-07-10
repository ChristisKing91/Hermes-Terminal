"""
Main application logic for Hermes Terminal
"""

import uuid
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

from .config import load_settings, create_default_config, load_hosts_config
from .models import CommandRisk, Command
from .safety.classifier import SafetyClassifier, ApprovalGate
from .audit.database import AuditDatabase
from .hosts.registry import HostRegistry
from .shell.executor import LocalExecutor, RemoteExecutor
from .ai.base import AIProvider
from .ai.ollama import OllamaProvider
from .ai.openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class HermesTerminal:
    """Main Hermes Terminal application"""

    def __init__(self):
        # Initialize configuration
        self.settings = load_settings()
        create_default_config()

        # Initialize components
        self.audit_db = AuditDatabase(self.settings.database_path)
        self.host_registry = HostRegistry()
        self.approval_gate = ApprovalGate()
        self.ai_provider = self._initialize_ai_provider()

        # Session state
        self.current_host = "gateway"
        self.current_user = "root"
        self.session_id = str(uuid.uuid4())
        self.session_active = False

    def _initialize_ai_provider(self) -> Optional[AIProvider]:
        """Initialize configured AI provider"""
        provider_type = self.settings.ai_provider.lower()

        if provider_type == "ollama":
            provider = OllamaProvider(
                base_url=self.settings.ollama_base_url,
                model=self.settings.ollama_model,
            )
            if provider.is_available():
                logger.info(f"Ollama provider ready: {self.settings.ollama_model}")
                return provider
            else:
                logger.warning(
                    f"Ollama not available at {self.settings.ollama_base_url} "
                    f"or model {self.settings.ollama_model} not found"
                )
                return None

        elif provider_type == "openai":
            if self.settings.openai_api_key and self.settings.openai_model:
                provider = OpenAICompatibleProvider(
                    api_key=self.settings.openai_api_key,
                    model=self.settings.openai_model,
                )
                if provider.is_available():
                    logger.info(f"OpenAI provider ready: {self.settings.openai_model}")
                    return provider
            logger.warning("OpenAI not properly configured")
            return None

        return None

    def start_session(self, mode: str = "manual") -> None:
        """Start a new session"""
        self.session_id = str(uuid.uuid4())
        self.audit_db.log_session(
            self.session_id, self.current_user, self.current_host, mode
        )
        self.session_active = True
        logger.info(f"Session started: {self.session_id}")

    def end_session(self) -> None:
        """End current session"""
        if self.session_active:
            self.audit_db.end_session(self.session_id)
            self.host_registry.close_all_connections()
            self.session_active = False
            logger.info(f"Session ended: {self.session_id}")

    def switch_host(self, host_name: str) -> bool:
        """Switch to a different host"""
        if host_name not in self.host_registry.list_hosts():
            logger.error(f"Unknown host: {host_name}")
            return False

        self.current_host = host_name
        logger.info(f"Switched to host: {host_name}")
        return True

    def execute_command(
        self, command: str, require_approval: bool = True
    ) -> tuple[int, str, str]:
        """Execute a command on the current host"""
        execution_id = str(uuid.uuid4())

        # Classify command
        risk_level, explanation = SafetyClassifier.classify(command)

        # Check if blocked
        if SafetyClassifier.is_blocked(risk_level):
            logger.warning(f"Blocked command: {command}")
            return 1, "", f"Command is blocked for safety: {explanation}"

        # Request approval if needed
        if require_approval and SafetyClassifier.requires_approval(risk_level):
            # In interactive mode, this would prompt the user
            # For now, we log it
            logger.warning(f"Command requires approval: {command}")
            return 1, "", "Command requires manual approval"

        # Get executor
        executor = self.host_registry.get_executor(self.current_host)
        if not executor:
            return 1, "", f"Failed to connect to {self.current_host}"

        # Log execution
        self.audit_db.log_execution(
            execution_id, self.session_id, command, self.current_host, self.current_user
        )

        # Execute
        try:
            exit_code, stdout, stderr = executor.execute(command)
            self.audit_db.log_execution_result(
                execution_id, exit_code, 0.0  # TODO: calculate duration
            )
            self.audit_db.log_output(
                str(uuid.uuid4()), execution_id, stdout, stderr
            )
            return exit_code, stdout, stderr
        except Exception as e:
            error_id = str(uuid.uuid4())
            self.audit_db.log_error(error_id, execution_id, str(e))
            return 1, "", str(e)

    def generate_command_plan(
        self, user_request: str
    ) -> Optional[dict]:
        """Use AI to generate a command plan"""
        if not self.ai_provider:
            logger.error("AI provider not available")
            return None

        request_id = str(uuid.uuid4())
        self.audit_db.log_user_request(
            request_id, self.session_id, user_request, self.current_host
        )

        try:
            response = self.ai_provider.generate_response(
                f"For the {self.current_host} system: {user_request}",
            )
            return {
                "request_id": request_id,
                "user_request": user_request,
                "ai_response": response,
                "host": self.current_host,
            }
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            return None

    def get_command_history(
        self, host: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """Get command history"""
        target_host = host or self.current_host
        return self.audit_db.get_command_history(target_host, limit)

    def get_failed_commands(self, limit: int = 50) -> list[dict]:
        """Get failed commands"""
        return self.audit_db.get_failed_commands(limit)
