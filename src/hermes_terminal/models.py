"""
Data models for Hermes Terminal
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class CommandRisk(str, Enum):
    """Command risk level classification"""
    SAFE = "safe"
    CAUTION = "caution"
    DANGER = "danger"
    BLOCKED = "blocked"


class ConnectionType(str, Enum):
    """Host connection type"""
    LOCAL = "local"
    SSH = "ssh"
    REMOTE = "remote"


class OperatingSystem(str, Enum):
    """Operating system type"""
    LINUX = "linux"
    KALI = "kali"
    PROXMOX = "proxmox"
    WINDOWS = "windows"
    MACOS = "macos"
    FREEBSD = "freebsd"


class Command(BaseModel):
    """Represents a command execution"""
    command: str
    risk_level: CommandRisk
    host: str
    explanation: str = ""
    timestamp: Optional[str] = None
    exit_code: Optional[int] = None
    output: Optional[str] = None


class HostConfig(BaseModel):
    """Host configuration"""
    name: str
    connection: ConnectionType
    hostname: Optional[str] = None
    user: Optional[str] = None
    port: int = 22
    operating_system: OperatingSystem = OperatingSystem.LINUX
    ssh_key: Optional[str] = None
    timeout: int = 30
    description: str = ""


class SessionRecord(BaseModel):
    """Session record for audit trail"""
    session_id: str
    user: str
    host: str
    mode: str  # manual, ai_assistant, command_builder
    start_time: str
    end_time: Optional[str] = None
    commands_executed: int = 0
    commands_approved: int = 0
    commands_rejected: int = 0


class ExecutionRecord(BaseModel):
    """Execution record"""
    execution_id: str
    session_id: str
    command: str
    host: str
    user: str
    start_time: str
    end_time: Optional[str] = None
    exit_code: Optional[int] = None
    duration_seconds: Optional[float] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
