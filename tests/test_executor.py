"""
Tests for shell execution (local and SSH)
"""

import pytest
from hermes_terminal.shell.executor import LocalExecutor


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
        exit_code, stdout, stderr = executor.execute("false")

        assert exit_code != 0

    def test_execute_with_error_output(self):
        """Test command that produces error output"""
        executor = LocalExecutor()
        exit_code, stdout, stderr = executor.execute("ls /nonexistent_directory")

        assert exit_code != 0
        assert "cannot access" in stderr.lower() or "no such" in stderr.lower()

    def test_execute_timeout(self):
        """Test command timeout"""
        executor = LocalExecutor()
        exit_code, stdout, stderr = executor.execute("sleep 10", timeout=1)

        # Should timeout
        assert exit_code == 124  # Standard timeout exit code

    def test_change_directory(self):
        """Test directory change"""
        executor = LocalExecutor("/tmp")
        cwd = executor.get_cwd()
        assert "/tmp" in cwd

        # Change to home
        success = executor.change_directory("~")
        assert success is True

    def test_invalid_directory_change(self):
        """Test invalid directory change"""
        executor = LocalExecutor()
        success = executor.change_directory("/nonexistent_directory_xyz")
        assert success is False
