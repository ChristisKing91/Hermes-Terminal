"""
Tests for audit database
"""

import pytest
from pathlib import Path
from hermes_terminal.audit.database import AuditDatabase


class TestAuditDatabase:
    """Test audit database operations"""

    def test_database_initialization(self, temp_db_path):
        """Test database initialization creates tables"""
        db = AuditDatabase(temp_db_path)
        assert temp_db_path.exists()

    def test_log_session(self, temp_db_path):
        """Test session logging"""
        db = AuditDatabase(temp_db_path)
        db.log_session("session1", "user1", "host1", "manual")

        # Verify we can retrieve it
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", ("session1",))
            row = cursor.fetchone()
            assert row is not None
            assert row["user"] == "user1"

    def test_log_execution(self, temp_db_path):
        """Test command execution logging"""
        db = AuditDatabase(temp_db_path)
        db.log_session("session1", "user1", "host1", "manual")
        db.log_execution("exec1", "session1", "ls -la", "host1", "user1")

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM executions WHERE execution_id = ?", ("exec1",))
            row = cursor.fetchone()
            assert row is not None
            assert row["command"] == "ls -la"

    def test_redact_secrets(self):
        """Test secret redaction"""
        text = "password=secret123 api_key=abc123 token=xyz789"
        redacted = AuditDatabase._redact_secrets(text)

        assert "***REDACTED***" in redacted
        assert "secret123" not in redacted
        assert "abc123" not in redacted
        assert "xyz789" not in redacted

    def test_get_command_history(self, temp_db_path):
        """Test retrieving command history"""
        db = AuditDatabase(temp_db_path)
        db.log_session("session1", "user1", "host1", "manual")
        db.log_execution("exec1", "session1", "ls", "host1", "user1")
        db.log_execution("exec2", "session1", "pwd", "host1", "user1")
        db.log_execution_result("exec1", 0, 0.5)
        db.log_execution_result("exec2", 0, 0.3)

        history = db.get_command_history("host1", limit=10)
        assert len(history) == 2
        assert history[0]["command"] == "pwd"  # Most recent first
