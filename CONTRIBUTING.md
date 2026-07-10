# Contributing to Hermes Terminal

Thank you for your interest in contributing to Hermes Terminal! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Welcome new contributors
- Report issues privately if needed

## Getting Started

### Prerequisites
- Python 3.11+
- Git
- Basic familiarity with terminal/CLI

### Setup Development Environment

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/Hermes-Terminal.git
cd Hermes-Terminal

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Verify installation
hermes doctor
```

### Configure for Development

```bash
# Copy example configs
cp .env.example .env
cp config/hosts.example.yaml ~/.config/hermes-terminal/hosts.yaml

# Edit .env for local development
HERMES_AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=neural-chat:latest
```

## Types of Contributions

### Bug Reports

**Before reporting:**
- Check if issue already exists
- Reproduce with minimal example
- Test with latest code

**When reporting:**
1. Clear, descriptive title
2. Steps to reproduce
3. Expected vs actual behavior
4. Environment (OS, Python version, etc.)
5. Relevant logs

### Feature Requests

**When requesting:**
1. Clear problem statement
2. Proposed solution
3. Example use case
4. Potential impact/complexity
5. Willing to implement?

### Code Contributions

#### Small Changes (typos, small fixes)
1. Fork repository
2. Create branch: `git checkout -b fix/typo-in-docs`
3. Make changes
4. Test locally
5. Submit PR

#### Medium Changes (new feature, refactoring)
1. Open issue first to discuss
2. Get feedback from maintainers
3. Fork and create branch
4. Follow development guide
5. Write tests
6. Document changes
7. Submit PR

#### Large Changes (new subsystem, major refactor)
1. Open issue with detailed proposal
2. Get maintainer buy-in
3. Create detailed design document
4. Implement with continuous feedback
5. Comprehensive testing
6. Full documentation
7. Submit PR

## Development Workflow

### Branch Naming

```
feature/description      # New feature
fix/issue-number         # Bug fix
refactor/description     # Code refactoring
docs/description         # Documentation
test/description         # Test additions
```

### Commit Messages

```
Short summary (50 chars max)

Optional detailed explanation (wrap at 72 chars)

Fixes #123
Related to #456
```

### Code Style

**Follow PEP 8 conventions:**

```bash
# Format with black
black src/

# Lint with ruff
ruff check src/ --fix

# Type check with mypy
mypy src/hermes_terminal/
```

### Testing

**Write tests for:**
- New features
- Bug fixes
- Edge cases
- Error conditions

**Test structure:**
```python
import pytest

class TestFeatureName:
    """Tests for feature name"""
    
    def test_happy_path(self):
        """Test normal operation"""
        # Arrange
        # Act
        # Assert
        pass
    
    def test_error_case(self):
        """Test error handling"""
        pass
```

**Running tests:**
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/hermes_terminal

# Run specific test
pytest tests/test_safety.py::TestSafetyClassifier::test_safe_commands -v
```

### Documentation

**Document:**
- New features in README.md
- API changes in DEVELOPMENT.md
- Architecture in ARCHITECTURE.md
- Usage examples in code comments

## Pull Request Process

### Before Submitting

1. **Update from main**
   ```bash
   git fetch origin
   git rebase origin/main
   ```

2. **Run full test suite**
   ```bash
   pytest tests/ -v
   ```

3. **Code quality checks**
   ```bash
   black src/
   ruff check src/ --fix
   mypy src/hermes_terminal/
   ```

4. **Update documentation**
   - README.md for user-facing changes
   - DEVELOPMENT.md for architecture changes
   - Docstrings for API changes

### Creating PR

1. Push to your fork
2. Go to GitHub and create PR
3. Use template below
4. Link related issues
5. Request review

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation

## Related Issues
Fixes #123
Related to #456

## Testing
- [ ] Added tests
- [ ] All tests pass
- [ ] Tested locally

## Documentation
- [ ] Updated README
- [ ] Updated docstrings
- [ ] Added examples

## Checklist
- [ ] Code follows style guidelines
- [ ] No security issues
- [ ] No breaking changes without discussion
```

## Review Process

### What Reviewers Look For
1. Code quality and style
2. Test coverage
3. Documentation
4. Security implications
5. Performance impact
6. API consistency
7. Backwards compatibility

### Addressing Feedback
1. Don't take feedback personally
2. Ask for clarification if needed
3. Make requested changes
4. Respond to comments
5. Re-request review

## Areas for Contribution

### Good First Issues
- [ ] Expand safety patterns
- [ ] Add host types
- [ ] Improve documentation
- [ ] Add test coverage
- [ ] Bug fixes

### Help Needed
- [ ] Web UI development
- [ ] Performance optimization
- [ ] New AI providers
- [ ] Platform-specific fixes (Windows, macOS)
- [ ] Kubernetes integration

## Reporting Security Issues

**DO NOT** open public issues for security vulnerabilities.

Email security concerns to: [maintainer-email]

Include:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Your contact information

## Community

### Getting Help
- GitHub Discussions for questions
- Issues for bugs and features
- Email for security
- Documentation for usage

### Staying Updated
- Watch repository for releases
- Star if you find it useful
- Share with others
- Give feedback

## Recognition

Contributors are recognized in:
- CONTRIBUTORS.md file
- Release notes
- GitHub profile
- Project README (for significant contributions)

## License

By contributing, you agree that your contributions will be licensed under the same MIT License as the project.

---

Thank you for contributing to Hermes Terminal! 🚀
