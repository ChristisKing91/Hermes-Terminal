"""
Data models for Hermes Terminal using Pydantic
"""

from enum import Enum
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class OperatingSystem(str, Enum):
    """Supported operating systems"""
    LINUX = "linux"
    KALI = "kali"
    PROXMOX = "proxmox"
    WINDOWS = "windows"


class ConnectionType(str, Enum):
    """Connection types"""
    LOCAL = "local"
    SSH = "ssh"


class CommandRisk(str, Enum):
    """Command risk classification"""
    SAFE = "safe"
    CAUTION = "caution"
    DANGER = "danger"
    BLOCKED = "blocked"


class HostConfig(BaseModel):
    """Configuration for a managed host"""
    model_config = ConfigDict(extra="allow")
    
    name: str
    description: str
    connection: ConnectionType = ConnectionType.SSH
    hostname: Optional[str] = None
    user: Optional[str] = None
    port: int = 22
    ssh_key: Optional[str] = None
    operating_system: OperatingSystem = OperatingSystem.LINUX
    timeout: int = 30
    enabled: bool = True


class Command(BaseModel):
    """A command to be executed"""
    command: str
    risk_level: CommandRisk
    explanation: str = ""
    host: str
    requires_approval: bool = False
    requires_confirmation: bool = False
    confirmation_text: Optional[str] = None


class CommandApproval(BaseModel):
    """Approval record for a command"""
    command_id: str
    user: str
    approved: bool
    timestamp: datetime = Field(default_factory=datetime.now)
    reason: Optional[str] = None


class CommandExecution(BaseModel):
    """Record of a command execution"""
    execution_id: str
    command: str
    host: str
    user: str
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0


class Session(BaseModel):
    """A session record"""
    session_id: str
    user: str
    host: str
    mode: str  # "manual", "ai_assistant", "command_builder"
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    working_directory: str = "~"
    commands_count: int = 0


class AIRequest(BaseModel):
    """AI assistant request"""
    request_id: str
    user_request: str
    host: str
    timestamp: datetime = Field(default_factory=datetime.now)
    context: Optional[dict[str, Any]] = None


class AIResponse(BaseModel):
    """AI assistant response"""
    request_id: str
    explanation: str
    commands: list[Command]
    risk_assessment: str
    timestamp: datetime = Field(default_factory=datetime.now)
    raw_response: Optional[str] = None
