"""
Tests for shell execution (local and SSH)
"""

import os
import shlex
import subprocess
import sys
from pathlib import Path

from hermes_terminal.shell.executor import LocalExecutor


def python_command(source):
    """Quote a small Python command for the platform's command shell."""
    args = [sys.executable, "-c", source]
    return subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)


class TestLocalExecutor:
    """Test local command execution"""

    def test_execute_success(self):
        """Test successful command execution"""
        executor = LocalExecutor()
        exit_code, stdout, stderr = executor.execute("echo 'hello world'")

        assert exit_code == 0
        assert "hello world" in stdout
        assert stderr == ""

    def test_execute_failure(self):
        """Test failed command execution"""
        executor = LocalExecutor()
        exit_code, stdout, stderr = executor.execute(python_command("raise SystemExit(3)"))

        assert exit_code == 3

    def test_execute_with_error_output(self):
        """Test command that produces error output"""
        executor = LocalExecutor()
        exit_code, stdout, stderr = executor.execute(
            python_command(
                "import sys; print('expected command error', file=sys.stderr); sys.exit(7)"
            )
        )

        assert exit_code == 7
        assert stdout == ""
        assert stderr.strip() == "expected command error"

    def test_execute_timeout(self):
        """Test command timeout"""
        executor = LocalExecutor()
        exit_code, stdout, stderr = executor.execute(
            python_command("import time; time.sleep(2)"), timeout=1
        )

        # Should timeout
        assert exit_code == 124  # Standard timeout exit code
        assert stdout == ""
        assert "timed out" in stderr.lower()

    def test_change_directory(self, tmp_path):
        """Test directory change"""
        executor = LocalExecutor(str(tmp_path))
        cwd = executor.get_cwd()
        assert Path(cwd).resolve() == tmp_path.resolve()

        # Change to home
        success = executor.change_directory("~")
        assert success is True
        assert Path(executor.get_cwd()).resolve() == Path.home().resolve()

    def test_invalid_directory_change(self):
        """Test invalid directory change"""
        executor = LocalExecutor()
        success = executor.change_directory("/nonexistent_directory_xyz")
        assert success is False
