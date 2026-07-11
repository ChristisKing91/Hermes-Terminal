"""
Enhanced Hermes Terminal with AI learning and context management
"""

import uuid
import logging
import time
from typing import Optional

from .config import load_settings, create_default_config
from .models import CommandRisk
from .safety.classifier import SafetyClassifier, ApprovalGate
from .audit.database import AuditDatabase
from .hosts.registry import HostRegistry
from .ai.base import AIProvider
from .ai.ollama import AITimeoutError, OllamaProvider
from .ai.openai_compatible import OpenAICompatibleProvider
from .learning.context import ContextManager
from .ai.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class HermesTerminal:
    """Enhanced Hermes Terminal with AI learning and memory"""

    def __init__(self):
        # Initialize configuration
        self.settings = load_settings()
        create_default_config()

        # Initialize core components
        self.audit_db = AuditDatabase(self.settings.database_path)
        self.host_registry = HostRegistry()
        self.approval_gate = ApprovalGate()
        self.ai_provider = self._initialize_ai_provider()

        # Initialize learning and context system
        self.context_manager = ContextManager(
            context_file=self.settings.context_file,
            session_log=self.settings.session_log,
            learning_batch_size=self.settings.learning_batch_size,
        )

        # Session state
        self.current_host = "gateway"
        self.current_user = "root"
        self.session_id = str(uuid.uuid4())
        self.session_active = False
        self.command_count = 0

        logger.info("Hermes Terminal initialized with learning system")
        self._review_context_on_startup()

    def _review_context_on_startup(self) -> None:
        """
        Review all learned context and session history on startup.
        This allows the AI to have full awareness of what's been done before.
        """
        logger.info("Reviewing learned context and session history...")

        # Log ongoing tasks
        ongoing = self.context_manager.get_ongoing_tasks()
        if ongoing:
            logger.info(f"Found {len(ongoing)} ongoing tasks:")
            for task in ongoing:
                logger.info(f"  - {task.get('description', 'Unknown')} (started {task.get('started_at', '?')})")

        # Check host profiles
        host_profiles = self.context_manager.context_data.get("host_profiles", {})
        if host_profiles:
            logger.info(f"Host profiles for {len(host_profiles)} machines:")
            for host, profile in host_profiles.items():
                logger.info(f"  - {host}: {profile}")

        # Report learned patterns
        successes = self.context_manager.context_data.get("successful_patterns", [])
        failures = self.context_manager.context_data.get("failed_patterns", [])
        logger.info(f"Learned patterns - Successful: {len(successes)}, Failed: {len(failures)}")

        # Report solutions
        solutions = self.context_manager.context_data.get("learned_solutions", [])
        if solutions:
            logger.info(f"Remembered {len(solutions)} solutions from previous sessions")

    def _initialize_ai_provider(self) -> Optional[AIProvider]:
        """Initialize configured AI provider with optimal settings"""
        provider_type = self.settings.ai_provider.lower()

        if provider_type == "ollama":
            provider = OllamaProvider(
                base_url=self.settings.ollama_base_url,
                model=self.settings.ollama_model,
                timeout=self.settings.ai_timeout,
            )
            if provider.is_available():
                logger.info(
                    f"Ollama provider ready: {self.settings.ollama_model} "
                    f"at {self.settings.ollama_base_url}"
                )
                return provider
            else:
                logger.warning(
                    f"Ollama not available at {self.settings.ollama_base_url} "
                    f"or model {self.settings.ollama_model} not found. "
                    f"Install with: ollama pull {self.settings.ollama_model}"
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
            logger.warning("OpenAI not properly configured (missing API key or model)")
            return None

        return None

    def start_session(self, mode: str = "manual") -> None:
        """Start a new session with context awareness"""
        self.session_id = str(uuid.uuid4())
        self.audit_db.log_session(
            self.session_id, self.current_user, self.current_host, mode
        )
        self.session_active = True
        self.command_count = 0
        logger.info(
            f"Session started: {self.session_id} in {mode} mode "
            f"on {self.current_host}"
        )

    def end_session(self) -> None:
        """End current session and save learning"""
        if self.session_active:
            self.audit_db.end_session(self.session_id)
            self.host_registry.close_all_connections()
            self.session_active = False
            self.context_manager._save_context()
            logger.info(
                f"Session ended: {self.session_id}. "
                f"Executed {self.command_count} commands."
            )

    def switch_host(self, host_name: str) -> bool:
        """Switch to a different host and load its context"""
        if host_name not in self.host_registry.list_hosts():
            logger.error(f"Unknown host: {host_name}")
            return False

        self.current_host = host_name
        logger.info(f"Switched to host: {host_name}")

        # Load host-specific context
        host_profile = self.context_manager.context_data.get("host_profiles", {}).get(
            host_name, {}
        )
        if host_profile:
            logger.info(f"Loaded context for {host_name}: {host_profile}")

        return True

    def execute_command(
        self, command: str, require_approval: bool = True
    ) -> tuple[int, str, str]:
        """Execute a command with safety classification and learning"""
        execution_id = str(uuid.uuid4())
        start_time = time.time()

        # Classify command
        risk_level, explanation = SafetyClassifier.classify(command)

        # Check if blocked
        if SafetyClassifier.is_blocked(risk_level):
            logger.warning(f"Blocked command: {command}")
            return 1, "", f"Command is blocked for safety: {explanation}"

        # Request approval if needed
        if require_approval and SafetyClassifier.requires_approval(risk_level):
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
            duration = time.time() - start_time

            self.audit_db.log_execution_result(execution_id, exit_code, duration)
            self.audit_db.log_output(str(uuid.uuid4()), execution_id, stdout, stderr)

            # Learn from execution
            if self.settings.enable_learning:
                self.context_manager.learn_from_execution(
                    command=command,
                    host=self.current_host,
                    exit_code=exit_code,
                    result=stdout or stderr,
                    context=None,
                )

                # Update context periodically
                self.command_count += 1
                if self.command_count % self.settings.context_update_interval == 0:
                    self.context_manager._save_context()

            return exit_code, stdout, stderr
        except Exception as e:
            error_id = str(uuid.uuid4())
            self.audit_db.log_error(error_id, execution_id, str(e))
            self.context_manager.learn_from_execution(
                command=command,
                host=self.current_host,
                exit_code=1,
                result=str(e),
                context=None,
            )
            return 1, "", str(e)

    @staticmethod
    def classify_command(command: str) -> tuple[CommandRisk, str]:
        """Expose classification to interactive clients before execution."""
        return SafetyClassifier.classify(command)

    def generate_command_plan(
        self, user_request: str
    ) -> Optional[dict]:
        """Use AI to generate a command plan with learned context"""
        if not self.ai_provider:
            logger.error("AI provider not available")
            return None

        request_id = str(uuid.uuid4())

        # Get context for this request
        context = self.context_manager.get_context_for_ai(self.current_host, user_request)

        # Build enhanced system prompt with learned context
        enhanced_prompt = self.context_manager.build_system_prompt_with_context(
            SYSTEM_PROMPT, self.current_host
        )

        # Log the request
        self.audit_db.log_user_request(
            request_id, self.session_id, user_request, self.current_host, context
        )

        try:
            # Include context in the prompt
            context_info = self._format_context_for_prompt(context)
            full_prompt = f"{context_info}\n\nUser request: {user_request}"

            response = self.ai_provider.generate_response(
                full_prompt,
                system_prompt=enhanced_prompt,
            )

            if not response.strip():
                return None

            return {
                "request_id": request_id,
                "user_request": user_request,
                "ai_response": response,
                "host": self.current_host,
                "context_used": len(context.get("recent_commands", [])),
            }
        except AITimeoutError as e:
            logger.warning("AI generation timed out")
            return {"error": str(e), "ai_response": "", "commands_generated": False}
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            return None

    def _format_context_for_prompt(self, context: dict) -> str:
        """Format learned context for inclusion in AI prompt"""
        lines = []

        if context.get("host_profile"):
            lines.append("## Host Profile (from previous sessions)")
            for key, value in context["host_profile"].items():
                lines.append(f"- {key}: {value}")

        if context.get("recent_commands"):
            lines.append("\n## Recently Executed Commands")
            for cmd in context["recent_commands"][-5:]:
                lines.append(f"- {cmd}")

        if context.get("ongoing_tasks"):
            lines.append("\n## Ongoing Tasks")
            for task in context["ongoing_tasks"]:
                lines.append(f"- {task.get('description')}: Status {task.get('status')}")

        if context.get("learned_solutions"):
            lines.append("\n## Remembered Solutions")
            for sol in context["learned_solutions"]:
                lines.append(f"- Problem: {sol.get('problem')}")
                lines.append(f"  Solution: {sol.get('solution')[:100]}...")

        return "\n".join(lines) if lines else ""

    def get_command_history(
        self, host: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """Get command history"""
        target_host = host or self.current_host
        return self.audit_db.get_command_history(target_host, limit)

    def get_failed_commands(self, limit: int = 50) -> list[dict]:
        """Get failed commands"""
        return self.audit_db.get_failed_commands(limit)

    def track_task(
        self, description: str, details: Optional[dict] = None
    ) -> str:
        """Start tracking a task for continuity"""
        return self.context_manager.add_ongoing_task(description, details)

    def complete_task(self, task_id: str, summary: Optional[str] = None) -> bool:
        """Mark a task as completed"""
        return self.context_manager.complete_ongoing_task(task_id, summary)

    def remember_solution(
        self, problem: str, solution: str, host: Optional[str] = None
    ) -> None:
        """Remember a solution for future reference"""
        target_host = host or self.current_host
        self.context_manager.save_solution(problem, solution, target_host)
        logger.info(f"Remembered solution for: {problem}")
