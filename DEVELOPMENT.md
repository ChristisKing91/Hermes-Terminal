# Hermes Terminal - Development Guide

## Project Overview

Hermes Terminal is a sophisticated remote terminal control system combining:
- Manual shell access with safety classification
- AI-powered command suggestions and assistance
- Comprehensive audit logging and safety controls
- Machine learning from session history
- Multi-machine management via SSH

## Architecture

### Core Components

```
hermes-terminal/
├── app.py                    # Main application with learning integration
├── cli.py                    # CLI interface using Typer + Rich
├── config.py                 # Configuration and settings management
├── models.py                 # Pydantic data models
│
├── safety/
│   ├── classifier.py         # Command risk classification (SAFE/CAUTION/DANGER/BLOCKED)
│   └── approval_gate.py      # Approval workflow management
│
├── audit/
│   └── database.py           # SQLite audit logging
│
├── shell/
│   └── executor.py           # LocalExecutor and RemoteExecutor (SSH)
│
├── hosts/
│   └── registry.py           # Host configuration and connection management
│
├── ai/
│   ├── base.py              # AIProvider abstract base class
│   ├── ollama.py            # Ollama local LLM integration
│   ├── openai_compatible.py # OpenAI API support
│   └── prompts.py           # System prompts and templates
│
└── learning/
    └── context.py           # AI learning and context management
```

### Data Flow

```
┌─────────────┐
│ User Input  │
└──────┬──────┘
       │
       ▼
┌──────────────────────┐
│ Safety Classifier    │ ──► Risk Level (SAFE/CAUTION/DANGER/BLOCKED)
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Approval Gate        │ ──► User Confirmation (if needed)
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Shell Executor       │ ──► Execute Command (Local or SSH)
│ (Local/Remote)       │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Context Manager      │ ──► Learn from Execution
│ (Learning System)    │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Audit Database       │ ──► Log Everything
│ (SQLite)             │
└──────────────────────┘
```

## Key Features Explained

### 1. Safety Classification System

**File**: `safety/classifier.py`

Classifies commands into four categories:

- **SAFE**: Read-only operations (ls, cat, grep, df, ps, etc.)
- **CAUTION**: Modifying but reversible (apt install, chmod, systemctl, mkdir, etc.)
- **DANGER**: Destructive operations (rm -rf, mkfs, dd, qm destroy, etc.)
- **BLOCKED**: Explicitly forbidden (base64 -d in pipe, eval, shell injection, etc.)

**Pattern Matching**: Uses regex patterns for flexible classification

**Approval Workflow**:
1. SAFE commands execute immediately
2. CAUTION commands prompt for user confirmation
3. DANGER commands require special format: `CONFIRM <hostname> <action>`
4. BLOCKED commands are rejected automatically

### 2. Learning & Context System

**File**: `learning/context.py`

Enables Hermes to remember and improve over time:

#### Startup Behavior
```
On startup:
1. Load context.yaml (learned knowledge)
2. Load session_log.yaml (command history)
3. Review ongoing tasks
4. Display host profiles
5. Load learned solutions
6. Build enhanced AI prompts with full context
```

#### Learning Mechanisms

1. **Pattern Learning**
   - Tracks successful command patterns
   - Records failed patterns to avoid
   - Auto-updates on each command execution

2. **Host Profiling**
   - Remembers OS, configuration, installed software
   - Tracks host-specific issues and solutions
   - Maintains state between sessions

3. **Solution Memory**
   - Saves problem-solution pairs
   - Indexes by problem and host
   - Reuses successful approaches

4. **Task Tracking**
   - Stores ongoing multi-step tasks
   - Allows resumption from where we left off
   - Maintains task state and progress

#### Context Building
```python
# On every AI request, build context from:
- Recent command history for current host
- Successful and failed commands
- Host profiles and discovered info
- Current ongoing tasks
- Remembered solutions
- System-wide knowledge
```

### 3. SSH Execution

**File**: `shell/executor.py`

- **LocalExecutor**: Run commands locally
- **RemoteExecutor**: SSH connections with key auth
- Working directory support for both
- Timeout handling
- Output capture (stdout/stderr)

### 4. Audit Database

**File**: `audit/database.py`

SQLite database with tables:
- `sessions`: Session metadata
- `executions`: Command execution records
- `outputs`: Command output/results
- `approvals`: Approval history
- `errors`: Error tracking
- `user_requests`: AI assistant requests
- `proposed_commands`: AI-generated commands

**Auto-redaction**: Sensitive data (passwords, keys, tokens) are redacted before logging

### 5. AI Integration

**File**: `ai/ollama.py` and `ai/openai_compatible.py`

#### Recommended: Ollama with neural-chat:latest

Why `neural-chat`?
- Optimized for dialog and instruction following
- Excellent context understanding
- Fast inference on modest hardware
- Can run locally without cloud dependencies
- Supports long context windows

#### Installation
```bash
# Install Ollama: https://ollama.ai
# Pull the recommended model
ollama pull neural-chat:latest

# Verify it's working
curl http://localhost:11434/api/tags
```

#### System Prompt Design

The system prompt is carefully crafted to:
1. Encourage inspection before changes
2. Prevent hallucination
3. Emphasize safety and data preservation
4. Provide clear step-by-step guidance
5. Explain commands and expected results

## Development Workflow

### Setup Development Environment

```bash
# Clone and install
git clone https://github.com/ChristisKing91/Hermes-Terminal.git
cd Hermes-Terminal
pip install -e ".[dev]"

# Setup pre-commit hooks (optional)
pre-commit install
```

### Configuration for Development

```bash
# Copy and edit .env
cp .env.example .env

# Edit for local Ollama
HERMES_AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=neural-chat:latest

# Copy hosts config
mkdir -p ~/.config/hermes-terminal
cp config/hosts.example.yaml ~/.config/hermes-terminal/hosts.yaml
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/hermes_terminal --cov-report=html

# Run specific test file
pytest tests/test_safety.py -v

# Run specific test
pytest tests/test_safety.py::TestSafetyClassifier::test_safe_commands -v
```

### Code Quality

```bash
# Format code with black
black src/

# Lint with ruff
ruff check src/ --fix

# Type checking
mypy src/hermes_terminal/

# All checks
make check  # if Makefile exists
```

## Adding New Features

### Example: Adding a New AI Provider

1. Create new file `src/hermes_terminal/ai/provider_name.py`
2. Inherit from `AIProvider` in `ai/base.py`
3. Implement `is_available()`, `generate_response()`, `list_models()`
4. Update `app.py` to handle new provider in `_initialize_ai_provider()`
5. Add configuration in `config.py`
6. Write tests in `tests/`

### Example: Adding Safety Patterns

Edit `safety/classifier.py`:

```python
# Add to appropriate list:
SAFE_PATTERNS = [
    r"^your_safe_command",  # Your safe command
    # ...
]

CAUTION_PATTERNS = [
    r"^your_caution_command",
    # ...
]

DANGER_PATTERNS = [
    r"dangerous_pattern",
    # ...
]

BLOCKED_PATTERNS = [
    r"forbidden_pattern",
    # ...
]
```

Then add tests in `tests/test_safety.py`.

### Example: Adding Host Types

1. Update `models.py` - add to `OperatingSystem` enum
2. Update `config.py` - handle in `load_hosts_config()`
3. Add OS-specific logic in `hosts/registry.py`
4. Document in `hosts.example.yaml`

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or via environment:
```bash
HERMES_LOG_LEVEL=DEBUG hermes
```

### Inspect Database

```bash
sqlite3 ~/.config/hermes-terminal/hermes.db
sqlite> SELECT * FROM executions LIMIT 10;
sqlite> SELECT * FROM approvals WHERE session_id = 'session-id';
```

### Check Context Files

```bash
cat ~/.config/hermes-terminal/context.yaml
cat ~/.config/hermes-terminal/session_log.yaml
```

### Test SSH Connection

```bash
# Verbose SSH connection test
ssh -vvv -i ~/.ssh/hermes_key user@hostname

# Test from Hermes
from hermes_terminal.shell.executor import RemoteExecutor
exec = RemoteExecutor('hostname', 'user', ssh_key_path='~/.ssh/hermes_key')
print(exec.connect())
```

## Performance Considerations

### Database Queries

- History queries are limited to last N commands (default: 50)
- Session searches filter by date for large databases
- Indexes on frequently queried columns (host, timestamp)

### AI Context

- Learning batch size configurable (default: 100 commands)
- Context window includes recent successful patterns
- Solutions filtered by relevance (host-specific first)

### SSH Connections

- Connection pooling in `HostRegistry`
- Connections kept open for session duration
- Configurable timeouts per host

## Security Best Practices

### For Users

1. **SSH Keys Only**: Never use password authentication
2. **Key Permissions**: `chmod 600 ~/.ssh/hermes_key`
3. **Regular Audits**: Review `audit_database.db` periodically
4. **Backups**: Before any dangerous operation
5. **Testing**: Test on non-production first

### For Developers

1. **No Secrets in Code**: Use environment variables
2. **Input Validation**: Always validate user input
3. **Error Handling**: Catch and log exceptions properly
4. **Code Review**: Get peer review before merge
5. **Security Tests**: Add tests for new safety patterns

## Troubleshooting Common Issues

### Issue: "Ollama not available"

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# If not running:
ollama serve  # In another terminal

# Check model is installed
ollama list

# Pull if missing
ollama pull neural-chat:latest
```

### Issue: SSH connection fails

```bash
# Verify host config
cat ~/.config/hermes-terminal/hosts.yaml

# Test connection manually
ssh -i ~/.ssh/hermes_key user@hostname

# Check key permissions
ls -la ~/.ssh/hermes_key  # Should be 600

# Check target host SSH
sudo systemctl status ssh
```

### Issue: Database locked

```bash
# Another process may be accessing it
lsof ~/.config/hermes-terminal/hermes.db

# Or close all Hermes processes and restart
pkill -f hermes
hermes
```

## Contributing Guidelines

1. **Fork** the repository
2. **Create feature branch**: `git checkout -b feature/description`
3. **Write tests** for new functionality
4. **Follow code style**: Black, Ruff, Mypy
5. **Document changes**: Update README/docs as needed
6. **Commit clearly**: Descriptive commit messages
7. **Push to branch**: `git push origin feature/description`
8. **Open Pull Request**: Describe changes and testing

## Release Process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create git tag: `git tag v0.2.0`
4. Push tag: `git push origin v0.2.0`
5. GitHub Actions builds and publishes to PyPI

## Resources

- **Typer Docs**: https://typer.tiangolo.com/
- **Rich Docs**: https://rich.readthedocs.io/
- **Pydantic Docs**: https://docs.pydantic.dev/
- **Paramiko Docs**: https://www.paramiko.org/
- **Ollama**: https://ollama.ai/
- **OpenAI API**: https://platform.openai.com/docs/

## Future Roadmap

- [ ] Web UI (FastAPI + React)
- [ ] Multi-user with RBAC
- [ ] Scheduled command execution
- [ ] Slack/Discord notifications
- [ ] Advanced analytics dashboard
- [ ] Command templating system
- [ ] Team collaboration features
- [ ] Mobile app

## Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Documentation**: See README.md

---

**Last Updated**: July 2026
**Version**: 0.1.0
