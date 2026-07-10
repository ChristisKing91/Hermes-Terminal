# Hermes Terminal - Complete Architecture Guide

## System Overview

Hermes Terminal is an intelligent remote terminal control system that combines:

1. **Command Safety**: Automatic classification and approval workflow
2. **AI Assistance**: OpenAI/Ollama integration for intelligent suggestions
3. **Learning System**: Remembers previous work and learns from experience
4. **Audit Trail**: Complete logging of all actions for compliance
5. **Multi-Host Management**: Control many machines from one interface

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Hermes Terminal CLI                       │
│  (Interactive menu, Manual shell, AI Assistant, Command Builder)
└────────────────────┬─────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
  ┌──────────────┐        ┌──────────────────┐
  │   Manual     │        │  AI Assistant    │
  │   Shell      │        │  (Context-aware) │
  └──────┬───────┘        └────────┬─────────┘
         │                         │
         └──────────┬──────────────┘
                    ▼
         ┌──────────────────────┐
         │ Safety Classifier    │
         │ (Risk Assessment)    │
         └──────────┬───────────┘
                    ▼
         ┌──────────────────────┐
         │ Approval Gate        │
         │ (User Confirmation)  │
         └──────────┬───────────┘
                    ▼
         ┌──────────────────────┐
         │ Command Executor     │
         │ (Local or SSH)       │
         └──────────┬───────────┘
                    ▼
    ┌───────────────┴───────────────┐
    ▼                               ▼
┌─────────────┐             ┌──────────────┐
│Local Shell  │             │SSH Connections│
└─────────────┘             │(Multi-host)  │
                            └──────────────┘
                    ▼
         ┌──────────────────────┐
         │ Context Manager      │
         │ (AI Learning System) │
         │ - Patterns           │
         │ - Solutions          │
         │ - Host Profiles      │
         │ - Task Tracking      │
         └──────────┬───────────┘
                    ▼
         ┌──────────────────────┐
         │ Audit Database       │
         │ (SQLite)             │
         │ Complete History     │
         └──────────────────────┘
```

## Detailed Component Architecture

### 1. CLI Layer (`cli.py`)

**Responsibilities:**
- Interactive menu system (Typer)
- Beautiful formatting (Rich)
- User input handling
- Session management

**Commands:**
```
hermes              # Interactive menu
hermes manual       # Manual shell mode
hermes ai-mode      # AI assistant mode
hermes build        # Command builder
hermes hosts-list   # List hosts
hermes history      # Show history
hermes doctor       # Diagnostics
```

### 2. Application Layer (`app.py`)

**Class: HermesTerminal**

**Key Methods:**
- `start_session()` - Initialize session with context review
- `end_session()` - Cleanup and save learning
- `switch_host()` - Change target machine
- `execute_command()` - Run command with safety checks
- `generate_command_plan()` - AI-powered suggestions
- `track_task()` / `complete_task()` - Task management
- `remember_solution()` - Save learned solutions

**Integration Points:**
- ContextManager (learning)
- SafetyClassifier (safety)
- HostRegistry (hosts)
- AuditDatabase (logging)
- AIProvider (AI)

### 3. Safety System (`safety/`)

**SafetyClassifier**

Pattern-based classification:
```python
SAFE → {ls, cat, grep, df, ps, top, ...}
CAUTION → {apt, chmod, mkdir, systemctl, ...}
DANGER → {rm -rf, mkfs, dd, qm destroy, ...}
BLOCKED → {eval, base64 -d, pipe to shell, ...}
```

**ApprovalGate**

Workflow:
```
Command → Classify Risk → Check if needs approval
  ↓
  SAFE: Execute immediately
  CAUTION: Prompt user "Approve? (yes/no)"
  DANGER: Require "CONFIRM <host> <action>" format
  BLOCKED: Reject with message
```

### 4. Execution Layer (`shell/`)

**LocalExecutor**
- Run commands locally
- Subprocess-based
- Supports working directory changes
- Timeout handling

**RemoteExecutor**
- SSH connections (Paramiko)
- Key-based authentication
- Session persistence
- Remote working directory support

### 5. Host Management (`hosts/`)

**HostRegistry**
- Load host configs from YAML
- Manage connections (pooling)
- Get/close executors
- List available hosts

**Configuration Format:**
```yaml
hosts:
  gateway:
    connection: local
    description: "Local control"
  
  core:
    connection: ssh
    hostname: 192.168.1.84
    user: root
    port: 22
    ssh_key: ~/.ssh/hermes_key
    operating_system: proxmox
```

### 6. AI Layer (`ai/`)

**AIProvider Base Class**
- Abstract interface
- `is_available()` - Check provider ready
- `generate_response()` - Get AI output
- `list_models()` - Enumerate models

**OllamaProvider** (Recommended)
- Local LLM via Ollama
- Model: neural-chat:latest (default)
- No internet required
- Configurable base URL
- Model auto-detection

**OpenAICompatibleProvider**
- OpenAI API support
- Compatible with Azure OpenAI, etc.
- Requires API key
- Supports all OpenAI models

**Prompts**
- System prompt with safety guidelines
- Host-specific context injection
- Learning-enhanced prompts
- Inspection-before-change emphasis

### 7. Learning System (`learning/`)

**ContextManager**

Core Features:

1. **Startup Behavior**
   ```
   Load context.yaml (persistent knowledge)
   Load session_log.yaml (history)
   Build host profiles from prior sessions
   Compile successful/failed patterns
   Review ongoing tasks
   ```

2. **Pattern Learning**
   ```python
   command "apt update" succeeds
   → Add "apt" to successful_patterns
   → Next time user asks about apt, mention success
   ```

3. **Host Profiling**
   ```python
   Execute on host "core"
   Discover: Ubuntu 22.04, 32GB RAM, Proxmox
   Store in context.host_profiles['core']
   Reference in future suggestions
   ```

4. **Solution Memory**
   ```python
   User: "Fix Kali apt"
   AI: runs diagnostic, solves problem
   System: saves (problem, solution) pair
   Next Kali session: includes this solution in context
   ```

5. **Task Tracking**
   ```python
   User: "I need to install Docker and configure it"
   System: track_task("Docker installation", details)
   User closes terminal
   Next session: shows ongoing tasks
   AI includes task context in suggestions
   ```

**Persistent Files:**
- `~/.config/hermes-terminal/context.yaml` - Learned knowledge
- `~/.config/hermes-terminal/session_log.yaml` - Command history

### 8. Audit System (`audit/`)

**AuditDatabase**

Tables:
- `sessions` - Session records
- `executions` - Command execution log
- `outputs` - Command results
- `approvals` - Approval decisions
- `errors` - Error log
- `user_requests` - AI requests
- `proposed_commands` - AI suggestions

**Auto-Redaction:**
```regex
password=... → password=***REDACTED***
api_key=... → api_key=***REDACTED***
token=... → token=***REDACTED***
```

### 9. Configuration System (`config.py`)

**Settings (Pydantic)**
- Environment variables with HERMES_ prefix
- .env file support
- Type validation
- Default values

**Key Settings:**
```python
ai_provider = "ollama"  # or "openai"
ollama_model = "neural-chat:latest"
enable_learning = True
learning_batch_size = 100
context_update_interval = 10
require_dangerous_confirmation = True
```

## Data Flow Examples

### Example 1: Manual Shell Command

```
User: $ systemctl restart nginx
  ↓
CLI captures input
  ↓
SafetyClassifier.classify("systemctl restart nginx")
  ↓ CAUTION risk detected
  ↓
ApprovalGate requests approval
  ↓
User: yes
  ↓
RemoteExecutor.execute() → SSH to target host
  ↓ exit_code=0, stdout="" 
  ↓
AuditDatabase.log_execution()
  ↓
ContextManager.learn_from_execution()
  ↓ Add "systemctl" to successful_patterns
  ↓
Display result to user
```

### Example 2: AI Assistant Request

```
User: "Fix Kali apt repositories"
  ↓
CLI captures request
  ↓
ContextManager.get_context_for_ai()
  ↓ Returns: recent commands, host profile, solutions
  ↓
ContextManager.build_system_prompt_with_context()
  ↓ Enhanced prompt with history
  ↓
AIProvider.generate_response()
  ↓ Ollama processes with context
  ↓ Returns: diagnostic steps + commands
  ↓
AuditDatabase.log_user_request()
  ↓
Display AI response
  ↓
User executes suggested commands
  ↓
ContextManager.learn_from_execution()
  ↓ Record pattern + solution
  ↓
ContextManager._save_context()
```

### Example 3: Session Resumption

```
Session 1:
  User: "I need to install Docker"
  System: track_task("Docker setup", {...})
  User: $ docker --version
  System: Task still in progress, save context
  User: Closes Hermes
  
Session 2:
  System: Load context.yaml
  System: Review ongoing tasks
  System: Load host profiles
  Display: "Found 1 ongoing task: Docker setup"
  AI: Uses task context in suggestions
  User: "What's next for Docker?"
  AI: "Based on our previous work..." (references Session 1)
  User: $ docker run hello-world
  System: complete_task("Docker setup", summary)
```

## Key Design Decisions

### 1. Why Regex for Safety Classification?
- Fast pattern matching
- Explicit patterns (maintainable)
- No false negatives for dangerous commands
- Can be audited and tested

### 2. Why Local SQLite Database?
- No external dependencies
- Offline-capable
- Portable between machines
- Can be backed up easily
- Can query locally for analytics

### 3. Why YAML for Context Storage?
- Human-readable
- Structure matches Python dicts
- Easy to version control
- Can be edited manually if needed
- Compact format

### 4. Why Ollama Default?
- Runs completely locally
- No API key needed
- No external dependencies
- neural-chat is optimized for instructions
- Suitable for production use

### 5. Why Learning-Focused Architecture?
- Reduces user repetition
- Builds domain knowledge over time
- Remembers what works (and what doesn't)
- Enables session continuity
- Makes AI suggestions more relevant

## Security Architecture

### Layers of Safety

1. **Classification Layer**: Pattern-based risk assessment
2. **Approval Layer**: User confirmation for risky operations
3. **Execution Layer**: Safe command execution (no shell injection)
4. **Audit Layer**: Complete logging for accountability
5. **Redaction Layer**: Secret protection in logs

### SSH Security

- Key-based authentication only
- Optional custom SSH keys per host
- Connection pooling (one SSH per host/session)
- Paramiko security defaults
- Timeout protection

### Approval Format for Dangerous Commands

```
CONFIRM <hostname> <action>

Example:
CONFIRM core reboot
CONFIRM kali delete-directory
```

Format provides:
- Explicit acknowledgment
- Host confirmation (not wrong machine)
- Action description (no copy-paste blindness)

## Performance Characteristics

### Command Execution
- Local: <10ms overhead
- SSH: 50-200ms (network dependent)
- Classification: <1ms
- Approval prompt: user-dependent
- Logging: <5ms

### AI Generation
- Ollama (neural-chat:7b): 2-10 sec/response
- OpenAI: 0.5-3 sec/response
- Context building: <100ms
- Prompt generation: <10ms

### Database Operations
- Insert execution: <5ms
- Query history: <20ms (with indices)
- Bulk context review: <500ms

## Extensibility Points

### Add New AI Provider
```python
class MyProvider(AIProvider):
    def is_available(self) -> bool: ...
    def generate_response(self, prompt, system_prompt) -> str: ...
    def list_models(self) -> list[str]: ...
```

### Add New Command Patterns
```python
SAFE_PATTERNS.append(r"^my_safe_cmd")
CAUTION_PATTERNS.append(r"^my_caution_cmd")
```

### Add New Host Types
```python
class OperatingSystem(str, Enum):
    MY_OS = "my_os"
```

### Add Learning Rules
```python
def custom_learning_rule(execution_result):
    # Custom logic to extract patterns
    pass
```

## Deployment Considerations

### Single User (Local)
- Use `connection: local` for gateway
- SSH keys in `~/.ssh/`
- Database in `~/.config/`
- Good for personal use

### Team Deployment
- Shared Hermes instance (not recommended)
- Individual instances with shared context
- Central audit server (future)
- RBAC system (future)

### Production Infrastructure
- Audit database backups
- SSH key management system
- Centralized logging
- Access control
- Session review processes

## Monitoring & Observability

### Built-in Logging
- All operations logged to SQLite
- Secret redaction enabled
- Session-based tracking
- Error tracking

### CLI Diagnostics
```bash
hermes doctor  # Health check
```

### Query Audit
```bash
sqlite3 hermes.db "SELECT * FROM executions WHERE host = 'core' LIMIT 20;"
```

## Future Architecture Enhancements

1. **Web UI**: FastAPI + React dashboard
2. **Distributed Logging**: Central audit server
3. **Role-Based Access**: Multi-user with permissions
4. **Advanced Analytics**: Trends, anomalies
5. **Command Templates**: Save and reuse patterns
6. **Slack Integration**: Notifications and control
7. **Kubernetes Support**: Native k8s integration
8. **Database Replication**: Sync across instances

---

**Document Version**: 1.0
**Last Updated**: July 2026
**For**: Hermes Terminal v0.1.0
