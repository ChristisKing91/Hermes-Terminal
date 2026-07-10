"""
Configuration management for Hermes Terminal
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field
import yaml

from .models import HostConfig, ConnectionType, OperatingSystem

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # AI Provider
    ai_provider: str = Field(default="ollama", description="AI provider: ollama or openai")

    # Ollama Configuration
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama base URL",
    )
    ollama_model: str = Field(
        default="neural-chat:latest",
        description="Ollama model to use - neural-chat is optimized for dialog and has excellent context understanding",
    )

    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(default="gpt-4-turbo", description="OpenAI model to use")

    # Paths
    config_dir: Path = Field(
        default_factory=lambda: Path.home() / ".config" / "hermes-terminal",
        description="Configuration directory",
    )
    database_path: Path = Field(
        default_factory=lambda: Path.home() / ".config" / "hermes-terminal" / "hermes.db",
        description="Database path",
    )
    log_dir: Path = Field(
        default_factory=lambda: Path.home() / ".local" / "share" / "hermes-terminal" / "logs",
        description="Log directory",
    )
    context_file: Path = Field(
        default_factory=lambda: Path.home() / ".config" / "hermes-terminal" / "context.yaml",
        description="Context/learning file path",
    )
    session_log: Path = Field(
        default_factory=lambda: Path.home() / ".config" / "hermes-terminal" / "session_log.yaml",
        description="Session log for continuity",
    )

    # SSH
    ssh_key_path: str = Field(
        default="~/.ssh/hermes_key",
        description="Default SSH key path",
    )
    ssh_timeout: int = Field(default=30, description="SSH timeout in seconds")

    # Security
    require_dangerous_confirmation: bool = Field(
        default=True,
        description="Require explicit confirmation for dangerous commands",
    )
    dangerous_confirmation_prefix: str = Field(
        default="CONFIRM",
        description="Confirmation prefix for dangerous commands",
    )

    # Audit
    audit_enabled: bool = Field(default=True, description="Enable audit logging")
    audit_redact_enabled: bool = Field(default=True, description="Enable secret redaction in logs")

    # Learning
    enable_learning: bool = Field(
        default=True,
        description="Enable AI learning from session history",
    )
    learning_batch_size: int = Field(
        default=100,
        description="Number of past commands to include in context window",
    )
    context_update_interval: int = Field(
        default=10,
        description="Update context summary every N commands",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_prefix = "HERMES_"


def load_settings() -> Settings:
    """Load settings from environment"""
    # Load .env if it exists
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    return Settings()


def create_default_config() -> None:
    """Create default configuration directories and files"""
    settings = load_settings()

    # Create directories
    settings.config_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Configuration directory: {settings.config_dir}")
    logger.info(f"Database path: {settings.database_path}")


def load_hosts_config(config_path: Optional[Path] = None) -> dict[str, HostConfig]:
    """Load hosts configuration from YAML"""
    if config_path is None:
        settings = load_settings()
        config_path = settings.config_dir / "hosts.yaml"

    if not config_path.exists():
        logger.warning(f"Hosts config not found at {config_path}")
        # Return default gateway host
        return {
            "gateway": HostConfig(
                name="gateway",
                connection=ConnectionType.LOCAL,
                description="Local WSL gateway",
            )
        }

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)

        hosts = {}
        for name, config in data.get("hosts", {}).items():
            hosts[name] = HostConfig(
                name=name,
                connection=ConnectionType(config.get("connection", "ssh")),
                hostname=config.get("hostname"),
                user=config.get("user"),
                port=config.get("port", 22),
                operating_system=OperatingSystem(config.get("operating_system", "linux")),
                ssh_key=config.get("ssh_key"),
                timeout=config.get("timeout", 30),
                description=config.get("description", ""),
            )

        return hosts
    except Exception as e:
        logger.error(f"Failed to load hosts config: {e}")
        return {}
