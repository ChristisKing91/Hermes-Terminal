"""
Configuration management for Hermes Terminal
"""

import os
from pathlib import Path
from typing import Optional
import yaml
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from .models import HostConfig, OperatingSystem, ConnectionType


class HermesSettings(BaseSettings):
    """Main settings for Hermes Terminal"""
    
    # AI Provider
    ai_provider: str = "ollama"  # "ollama" or "openai"
    
    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"
    
    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    
    # Paths
    config_dir: Path = Field(default_factory=lambda: Path.home() / ".config" / "hermes-terminal")
    database_path: Path = Field(default_factory=lambda: Path.home() / ".config" / "hermes-terminal" / "hermes.db")
    log_dir: Path = Field(default_factory=lambda: Path.home() / ".local" / "share" / "hermes-terminal" / "logs")
    
    # SSH
    ssh_key_path: Path = Field(default_factory=lambda: Path.home() / ".ssh" / "hermes_key")
    ssh_timeout: int = 30
    
    # Security
    require_dangerous_confirmation: bool = True
    
    # Audit
    audit_enabled: bool = True
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_prefix = "HERMES_"
        case_sensitive = False


def load_settings() -> HermesSettings:
    """Load settings from environment"""
    # Load .env file if it exists
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    return HermesSettings()


def load_hosts_config(config_path: Optional[Path] = None) -> dict[str, HostConfig]:
    """Load hosts configuration from YAML file"""
    if config_path is None:
        settings = load_settings()
        config_path = settings.config_dir / "hosts.yaml"
    
    if not config_path.exists():
        return _get_default_hosts()
    
    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        
        if not data or "hosts" not in data:
            return _get_default_hosts()
        
        hosts = {}
        for name, config in data.get("hosts", {}).items():
            config["name"] = name
            hosts[name] = HostConfig(**config)
        
        return hosts
    except Exception as e:
        print(f"Error loading hosts config: {e}")
        return _get_default_hosts()


def _get_default_hosts() -> dict[str, HostConfig]:
    """Get default hosts configuration"""
    return {
        "gateway": HostConfig(
            name="gateway",
            connection=ConnectionType.LOCAL,
            description="Gateway WSL control node (local)",
        ),
        "core": HostConfig(
            name="core",
            hostname="192.168.1.84",
            user="root",
            port=22,
            description="Proxmox host",
            operating_system=OperatingSystem.PROXMOX,
        ),
        "kali": HostConfig(
            name="kali",
            hostname="192.168.1.100",
            user="roy",
            port=22,
            description="Kali VM 100",
            operating_system=OperatingSystem.KALI,
        ),
    }


def create_default_config():
    """Create default configuration directory and files"""
    settings = load_settings()
    
    # Create directories
    settings.config_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create hosts.yaml if it doesn't exist
    hosts_path = settings.config_dir / "hosts.yaml"
    if not hosts_path.exists():
        hosts_data = {
            "hosts": {
                "gateway": {
                    "connection": "local",
                    "description": "Gateway WSL control node (local)",
                },
                "core": {
                    "hostname": "192.168.1.84",
                    "user": "root",
                    "port": 22,
                    "description": "Proxmox host",
                    "operating_system": "proxmox",
                    "ssh_key": "~/.ssh/hermes_key",
                    "timeout": 30,
                },
                "kali": {
                    "hostname": "192.168.1.100",
                    "user": "roy",
                    "port": 22,
                    "description": "Kali VM 100",
                    "operating_system": "kali",
                    "ssh_key": "~/.ssh/hermes_key",
                    "timeout": 30,
                },
            }
        }
        with open(hosts_path, "w") as f:
            yaml.dump(hosts_data, f, default_flow_style=False)
    
    # Create policy.yaml if it doesn't exist
    policy_path = settings.config_dir / "policy.yaml"
    if not policy_path.exists():
        policy_data = {
            "safety_policy": {
                "enable_dangerous_confirmation": True,
                "dangerous_confirmation_prefix": "CONFIRM",
                "safe_commands": [
                    "pwd", "ls", "cat", "head", "tail", "grep", "find",
                    "df", "free", "uname", "ip addr", "systemctl status",
                    "journalctl", "apt-cache", "pvesm status", "qm config",
                    "qm status", "lvs", "vgs", "pvs", "lsblk",
                ],
                "caution_commands": [
                    "apt update", "apt install", "apt remove", "systemctl start",
                    "systemctl stop", "chmod", "chown", "useradd", "qm set",
                ],
                "dangerous_commands": [
                    "rm -rf", "dd", "mkfs", "wipefs", "fdisk", "lvremove",
                    "qm destroy", "shutdown", "reboot",
                ],
            }
        }
        with open(policy_path, "w") as f:
            yaml.dump(policy_data, f, default_flow_style=False)
