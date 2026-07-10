# Hermes Terminal 🧙‍♂️

A sophisticated remote terminal control system with integrated AI assistance for managing multiple machines via SSH. Hermes combines manual shell access, AI-powered command suggestions, and comprehensive safety/audit logging into a unified interface.

## Features

### 🎯 Core Capabilities
- **Multi-Machine Management**: Seamlessly switch between configured hosts (Proxmox, Kali, Linux systems)
- **Manual Shell Mode**: Direct terminal access with safety classification and approval gates
- **AI Assistant**: Ask the AI to help diagnose and solve infrastructure problems
- **AI Command Builder**: Describe desired outcomes and get AI-generated commands
- **Safety First**: Automatic command classification (safe/caution/danger) with approval workflows
- **Comprehensive Audit**: SQLite-based logging of all commands, sessions, and outcomes

### 🔒 Safety & Security
- **Command Risk Classification**: Regex-based patterns to classify commands as safe, caution, danger, or blocked
- **Approval Gates**: Dangerous commands require explicit confirmation with specific format
- **Secret Redaction**: Automatic detection and redaction of passwords, API keys, tokens from logs
- **Session Tracking**: Complete audit trail of all sessions, commands, and results
- **SSH Key Support**: Secure authentication via SSH keys with optional key-based auth

### 🤖 AI Integration
- **Ollama Support**: Local LLM inference via Ollama with model auto-detection
- **OpenAI Compatible**: Support for OpenAI API and compatible providers
- **Safe Prompting**: System prompts designed to encourage inspection before changes
- **Context Awareness**: AI understands system state and provides informed suggestions

## Quick Start

### Prerequisites
- Python 3.11+
- SSH access to target machines (optional for local gateway)
- Ollama running locally OR OpenAI API key

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/Hermes-Terminal.git
cd Hermes-Terminal

# Install in development mode
pip install -e .[dev]

# Copy and configure environment
cp .env.example .env
# Edit .env with your Ollama URL or OpenAI API key

# Copy and configure hosts
cp config/hosts.example.yaml ~/.config/hermes-terminal/hosts.yaml
# Edit hosts.yaml with your target machines
```

### Basic Usage

```bash
# Start interactive menu
hermes

# Start in manual shell mode
hermes manual

# Start in AI assistant mode (requires Ollama or OpenAI)
hermes ai-mode

# Start in command builder mode
hermes build

# List configured hosts
hermes hosts-list

# Show command history
hermes history

# Run diagnostic
hermes doctor
```

## Architecture

### Module Structure

```
hermes_terminal/
├── __init__.py              # Package initialization
├── app.py                   # Main application logic
├── cli.py                   # CLI interface with Typer
├── config.py                # Configuration management
├── models.py                # Pydantic data models
├── safety/
│   ├── __init__.py
│   └── classifier.py        # Command safety classification
├── audit/
│   ├── __init__.py
│   └── database.py          # SQLite audit database
├── shell/
│   ├── __init__.py
│   └── executor.py          # Local and SSH command execution
├── hosts/
│   ├── __init__.py
│   └── registry.py          # Host configuration and registry
└── ai/
    ├── __init__.py
    ├── base.py              # AI provider base class
    ├── ollama.py            # Ollama provider
    ├── openai_compatible.py # OpenAI provider
    └── prompts.py           # System prompts and templates
```

### Data Flow

1. **User Input** → CLI/Interactive prompt
2. **Command Classification** → Safety classifier (risk level determination)
3. **Approval Check** → ApprovalGate (user confirmation if needed)
4. **Execution** → LocalExecutor or RemoteExecutor via SSH
5. **Audit Logging** → AuditDatabase (SQLite)
6. **Result Display** → Rich console output

### Safety Classification

Commands are classified into four categories:

- **SAFE**: Read-only commands like `ls`, `cat`, `grep`, `df`, etc.
- **CAUTION**: System modification commands like `apt install`, `chmod`, `systemctl`, etc.
- **DANGER**: Destructive commands like `rm -rf`, `mkfs`, `lvremove`, `qm destroy`, etc.
- **BLOCKED**: Explicitly forbidden patterns like `base64 -d`, `eval`, pipe to shell, etc.

### Approval Workflow

For CAUTION and DANGER commands:

1. Command is flagged for approval
2. User is prompted: `[CAUTION/DANGER] Command requires approval`
3. For DANGER commands, explicit format required: `CONFIRM <hostname> <action>`
4. Approval logged with timestamp and reason
5. Command executed or rejected based on approval

## Configuration

### Environment Variables (.env)

```env
# AI Provider
HERMES_AI_PROVIDER=ollama  # ollama or openai

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b

# OpenAI Configuration (optional)
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4

# Paths
HERMES_CONFIG_DIR=~/.config/hermes-terminal
HERMES_DATABASE=hermes.db
HERMES_LOG_DIR=~/.local/share/hermes-terminal/logs

# SSH
HERMES_SSH_KEY_PATH=~/.ssh/hermes_key
HERMES_SSH_TIMEOUT=30

# Security
HERMES_REQUIRE_DANGEROUS_CONFIRMATION=true

# Audit
HERMES_AUDIT_ENABLED=true
```

### Host Configuration (hosts.yaml)

```yaml
hosts:
  gateway:
    connection: local
    description: "Gateway WSL control node"

  core:
    hostname: 192.168.1.84
    user: root
    port: 22
    description: "Proxmox host"
    operating_system: proxmox
    ssh_key: ~/.ssh/hermes_key
    timeout: 30

  kali:
    hostname: 192.168.1.100
    user: roy
    port: 22
    description: "Kali VM"
    operating_system: kali
    ssh_key: ~/.ssh/hermes_key
    timeout: 30
```

### Safety Policy (policy.yaml)

Customize command classification, blocked patterns, and approval requirements.

## Usage Modes

### 1. Manual Shell Mode

Direct terminal access with integrated safety checks:

```
[core] $ ls /var/log
[core] $ apt update
[CAUTION] Approval Required
Approve? (yes/no): yes
```

Special commands:
- `/host <name>` - Switch to different host
- `/ai` - Switch to AI Assistant mode
- `/build` - Switch to AI Command Builder mode
- `/exit` - Exit manual shell

### 2. AI Assistant Mode

Describe what you need, AI helps diagnose and suggest fixes:

```
What do you need? Fix Kali apt repositories

AI Response:
I'll help repair the Kali repository configuration.
First, let me inspect the current state...
```

### 3. AI Command Builder

Describe desired outcome, get AI-generated commands:

```
What do you want to achieve? Install Docker on Kali

Proposed Commands:
apt update
apt install -y docker.io
systemctl start docker

[r] Run  [e] Edit  [c] Copy  [s] Save  [x] Cancel
```

## Database Schema

### audit_database.db

**sessions** - Session tracking
- session_id, user, host, mode, start_time, end_time, working_directory, commands_count

**executions** - Command execution records
- execution_id, session_id, command_id, command, host, user, start_time, end_time, exit_code, duration_seconds

**outputs** - Command output storage
- output_id, execution_id, stdout, stderr, timestamp

**approvals** - Approval history
- approval_id, command_id, user, approved, reason, timestamp

**errors** - Error logging
- error_id, execution_id, error_message, error_type, timestamp

**user_requests** - AI requests
- request_id, session_id, user_request, target_host, timestamp, context

**proposed_commands** - AI-generated commands
- command_id, request_id, command, risk_level, explanation, timestamp

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
pytest tests/ --cov=src/hermes_terminal
```

### Code Quality

```bash
# Format code
black src/

# Lint
ruff check src/

# Type checking
mypy src/hermes_terminal/
```

### Project Structure for Development

```
tests/
├── test_safety.py           # Safety classifier tests
├── test_executor.py         # Shell executor tests
├── test_audit.py            # Audit database tests
├── test_cli.py              # CLI interface tests
└── conftest.py              # Pytest configuration
```

## Security Considerations

### What Hermes Does
✅ Logs all command execution with full audit trail
✅ Classifies commands by risk level
✅ Requires explicit approval for dangerous operations
✅ Redacts sensitive data (passwords, keys, tokens) from logs
✅ Supports SSH key authentication
✅ Enforces confirmation format for critical commands
✅ Tracks user, timestamp, and success/failure for each command

### What Hermes Does NOT Do
❌ Prevent users from running approved dangerous commands
❌ Protect against SSH compromise or credential theft
❌ Enforce network-based access controls
❌ Replace proper system administration practices
❌ Serve as a substitute for proper backup and recovery procedures

### Best Practices

1. **SSH Keys**: Always use SSH key authentication, never store passwords
2. **Testing**: Test commands on non-production systems first
3. **Backups**: Always backup before destructive operations
4. **Reviews**: Regularly review audit logs for unusual activity
5. **Least Privilege**: Use sudo only where needed
6. **Updates**: Keep systems and dependencies up to date

## Troubleshooting

### Ollama Connection Failed

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Verify model is installed
ollama list

# Pull the default model
ollama pull qwen2.5-coder:7b
```

### SSH Connection Issues

```bash
# Test SSH connection
ssh -v -i ~/.ssh/hermes_key user@hostname

# Check SSH key permissions
ls -la ~/.ssh/hermes_key  # Should be 600

# Verify SSH server is running
sudo systemctl status ssh
```

### Database Errors

```bash
# Check database location
echo $HERMES_DATABASE_PATH

# Reset database (WARNING: Deletes audit history)
rm ~/.config/hermes-terminal/hermes.db
hermes  # Will recreate on startup
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see LICENSE file for details

## Author

**Christis King** - Infrastructure automation and AI integration

## Acknowledgments

- Typer for CLI framework
- Rich for beautiful terminal output
- Pydantic for data validation
- Paramiko for SSH functionality
- Ollama for local LLM inference
- OpenAI for API compatibility

## Roadmap

- [ ] Web interface (FastAPI + React)
- [ ] Multi-user support with role-based access control
- [ ] Scheduled command execution
- [ ] Ansible integration
- [ ] Terraform integration
- [ ] Slack/Discord notifications
- [ ] Advanced command templates and macros
- [ ] Performance monitoring and alerting
- [ ] Database query builder for complex reports
- [ ] Mobile app for basic operations

## Support

For issues, questions, or suggestions:

1. Check existing [GitHub Issues](https://github.com/yourusername/Hermes-Terminal/issues)
2. Create a new issue with detailed information
3. Include logs from `~/.local/share/hermes-terminal/logs/`

---

**Last Updated**: July 2026
**Version**: 0.1.0 (Beta)
