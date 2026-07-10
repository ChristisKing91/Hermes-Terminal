"""
AI context and learning system for continuous improvement
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Any
import yaml

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages AI context and learning from session history"""

    def __init__(self, context_file: Path, session_log: Path, learning_batch_size: int = 100):
        self.context_file = context_file
        self.session_log = session_log
        self.learning_batch_size = learning_batch_size
        self.context_data = self._load_context()
        self.session_history = self._load_session_history()

    def _load_context(self) -> dict[str, Any]:
        """Load existing context file"""
        if self.context_file.exists():
            try:
                with open(self.context_file) as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load context: {e}")
                return {}
        return self._initialize_context()

    def _initialize_context(self) -> dict[str, Any]:
        """Create initial context structure"""
        return {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "system_knowledge": {},
            "host_profiles": {},
            "command_patterns": [],
            "failed_patterns": [],
            "successful_patterns": [],
            "user_preferences": {},
            "ongoing_tasks": [],
            "learned_solutions": [],
        }

    def _load_session_history(self) -> list[dict]:
        """Load session history for context"""
        if self.session_log.exists():
            try:
                with open(self.session_log) as f:
                    return yaml.safe_load(f) or []
            except Exception as e:
                logger.error(f"Failed to load session history: {e}")
                return []
        return []

    def build_system_prompt_with_context(self, base_prompt: str, current_host: str) -> str:
        """
        Build an enhanced system prompt with learned context.
        This is called at startup and during sessions.
        """
        context_summary = self._generate_context_summary(current_host)

        enhanced_prompt = f"""{base_prompt}

## LEARNED CONTEXT (from {len(self.session_history)} previous sessions)

{context_summary}

## CURRENT ENVIRONMENT
Target Host: {current_host}
Host Profile: {self._get_host_profile(current_host)}

## REMEMBERED PATTERNS
Successful approaches:
{self._format_successful_patterns()}

Patterns to avoid:
{self._format_failed_patterns()}

## ONGOING TASKS
{self._format_ongoing_tasks()}

Use this context to provide more accurate and relevant assistance.
If relevant to current task, reference previous successful solutions.
"""
        return enhanced_prompt

    def _generate_context_summary(self, current_host: str) -> str:
        """Generate summary of learned context"""
        summary_parts = []

        # System knowledge
        if self.context_data.get("system_knowledge"):
            summary_parts.append("### System Knowledge")
            for key, value in self.context_data["system_knowledge"].items():
                summary_parts.append(f"- {key}: {value}")

        # Host-specific knowledge
        if current_host in self.context_data.get("host_profiles", {}):
            summary_parts.append(f"\n### {current_host} Profile")
            profile = self.context_data["host_profiles"][current_host]
            for key, value in profile.items():
                summary_parts.append(f"- {key}: {value}")

        return "\n".join(summary_parts) if summary_parts else "No previous context available."

    def _get_host_profile(self, host: str) -> str:
        """Get host profile from context"""
        profile = self.context_data.get("host_profiles", {}).get(host, {})
        if not profile:
            return "No profile yet"
        return ", ".join(f"{k}: {v}" for k, v in profile.items())

    def _format_successful_patterns(self) -> str:
        """Format successful patterns for prompt"""
        patterns = self.context_data.get("successful_patterns", [])
        if not patterns:
            return "None yet"
        return "\n".join(f"- {p}" for p in patterns[:5])  # Show top 5

    def _format_failed_patterns(self) -> str:
        """Format failed patterns for prompt"""
        patterns = self.context_data.get("failed_patterns", [])
        if not patterns:
            return "None yet"
        return "\n".join(f"- {p}" for p in patterns[:5])  # Show top 5

    def _format_ongoing_tasks(self) -> str:
        """Format ongoing tasks for prompt"""
        tasks = self.context_data.get("ongoing_tasks", [])
        if not tasks:
            return "None"
        return "\n".join(f"- {t.get('description', 'Unknown')} (Started: {t.get('started_at', '?')})" for t in tasks[:3])

    def learn_from_execution(
        self,
        command: str,
        host: str,
        exit_code: int,
        result: Optional[str] = None,
        context: Optional[str] = None,
    ) -> None:
        """
        Learn from command execution.
        Track successful and failed patterns.
        """
        if exit_code == 0:
            self._record_success(command, host, result, context)
        else:
            self._record_failure(command, host, result, context)

    def _record_success(self, command: str, host: str, result: Optional[str], context: Optional[str]) -> None:
        """Record successful command execution"""
        # Update host profile
        if host not in self.context_data["host_profiles"]:
            self.context_data["host_profiles"][host] = {}

        # Extract and save patterns
        pattern = self._extract_pattern(command)
        if pattern not in self.context_data["successful_patterns"]:
            self.context_data["successful_patterns"].append(pattern)
            logger.debug(f"Learned successful pattern: {pattern}")

        # Save to session history
        self.session_history.append({
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "host": host,
            "status": "success",
            "context": context,
        })

    def _record_failure(self, command: str, host: str, result: Optional[str], context: Optional[str]) -> None:
        """Record failed command execution"""
        pattern = self._extract_pattern(command)
        if pattern not in self.context_data["failed_patterns"]:
            self.context_data["failed_patterns"].append(pattern)
            logger.debug(f"Learned failed pattern: {pattern}")

        # Save to session history
        self.session_history.append({
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "host": host,
            "status": "failure",
            "error": result,
            "context": context,
        })

    def _extract_pattern(self, command: str) -> str:
        """Extract generalizable pattern from command"""
        # Simple pattern extraction - could be enhanced
        parts = command.split()
        if parts:
            return parts[0]  # Use the base command
        return command

    def add_ongoing_task(self, task_description: str, details: Optional[dict] = None) -> str:
        """Add task to ongoing tasks"""
        task_id = f"task_{datetime.now().timestamp()}"
        task = {
            "id": task_id,
            "description": task_description,
            "started_at": datetime.now().isoformat(),
            "details": details or {},
            "status": "in_progress",
        }
        self.context_data["ongoing_tasks"].append(task)
        self._save_context()
        return task_id

    def complete_ongoing_task(self, task_id: str, summary: Optional[str] = None) -> bool:
        """Mark task as completed"""
        for task in self.context_data["ongoing_tasks"]:
            if task["id"] == task_id:
                task["status"] = "completed"
                task["completed_at"] = datetime.now().isoformat()
                if summary:
                    task["summary"] = summary
                self._save_context()
                return True
        return False

    def get_ongoing_tasks(self) -> list[dict]:
        """Get current ongoing tasks"""
        return [t for t in self.context_data.get("ongoing_tasks", []) if t.get("status") == "in_progress"]

    def record_host_discovery(self, host: str, info: dict[str, Any]) -> None:
        """Record discovered information about a host"""
        if host not in self.context_data["host_profiles"]:
            self.context_data["host_profiles"][host] = {}

        self.context_data["host_profiles"][host].update(info)
        self._save_context()
        logger.debug(f"Updated host profile for {host}")

    def record_system_knowledge(self, key: str, value: Any) -> None:
        """Record general system knowledge"""
        self.context_data["system_knowledge"][key] = value
        self._save_context()
        logger.debug(f"Recorded system knowledge: {key}")

    def save_solution(self, problem: str, solution: str, host: Optional[str] = None) -> None:
        """Save a learned solution"""
        solution_record = {
            "problem": problem,
            "solution": solution,
            "host": host,
            "learned_at": datetime.now().isoformat(),
        }
        self.context_data["learned_solutions"].append(solution_record)
        self._save_context()
        logger.debug(f"Saved solution for: {problem}")

    def _save_context(self) -> None:
        """Save context to file"""
        try:
            self.context_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.context_file, "w") as f:
                self.context_data["updated_at"] = datetime.now().isoformat()
                yaml.dump(self.context_data, f, default_flow_style=False)

            # Also save session history
            self.session_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self.session_log, "w") as f:
                yaml.dump(self.session_history[-self.learning_batch_size:], f, default_flow_style=False)

            logger.debug("Context saved")
        except Exception as e:
            logger.error(f"Failed to save context: {e}")

    def get_context_for_ai(
        self, current_host: str, user_request: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Get relevant context to include in AI requests.
        Filters history for relevance.
        """
        recent_history = self.session_history[-self.learning_batch_size:]
        host_history = [
            h for h in recent_history if h.get("host") == current_host
        ][-10:]

        return {
            "host_profile": self.context_data.get("host_profiles", {}).get(current_host, {}),
            "recent_commands": [h.get("command") for h in host_history],
            "recent_successes": [h for h in host_history if h.get("status") == "success"],
            "recent_failures": [h for h in host_history if h.get("status") == "failure"],
            "ongoing_tasks": self.get_ongoing_tasks(),
            "learned_solutions": [
                s for s in self.context_data.get("learned_solutions", [])
                if s.get("host") in [None, current_host]
            ][-5:],
        }
