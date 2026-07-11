"""
Audit database for logging commands, sessions, and approvals
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class AuditDatabase:
    """SQLite-based audit log for Hermes Terminal"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_db()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def _initialize_db(self):
        """Create database schema if it doesn't exist"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user TEXT NOT NULL,
                    host TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    working_directory TEXT DEFAULT '~',
                    commands_count INTEGER DEFAULT 0
                )
            """)
            
            # Hosts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hosts (
                    host_name TEXT PRIMARY KEY,
                    hostname TEXT,
                    user TEXT,
                    port INTEGER DEFAULT 22,
                    operating_system TEXT,
                    last_accessed TIMESTAMP
                )
            """)
            
            # User requests (AI assistant mode)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_requests (
                    request_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_request TEXT NOT NULL,
                    target_host TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    context TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            
            # Proposed commands
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS proposed_commands (
                    command_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    command TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    explanation TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES user_requests(request_id)
                )
            """)
            
            # Approvals
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    command_id TEXT NOT NULL,
                    user TEXT NOT NULL,
                    approved BOOLEAN NOT NULL,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (command_id) REFERENCES proposed_commands(command_id)
                )
            """)
            
            # Executions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS executions (
                    execution_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    command_id TEXT,
                    command TEXT NOT NULL,
                    host TEXT NOT NULL,
                    user TEXT NOT NULL,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    exit_code INTEGER,
                    duration_seconds FLOAT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    FOREIGN KEY (command_id) REFERENCES proposed_commands(command_id)
                )
            """)
            
            # Command output
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS outputs (
                    output_id TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL,
                    stdout TEXT,
                    stderr TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
                )
            """)
            
            # Errors
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    error_id TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    error_type TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
                )
            """)
            
            conn.commit()
    
    def log_session(self, session_id: str, user: str, host: str, mode: str) -> None:
        """Log a new session"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (session_id, user, host, mode)
                VALUES (?, ?, ?, ?)
            """, (session_id, user, host, mode))
    
    def end_session(self, session_id: str) -> None:
        """End a session"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sessions SET end_time = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, (session_id,))
    
    def log_user_request(
        self,
        request_id: str,
        session_id: str,
        user_request: str,
        target_host: str,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log a user request to the AI assistant"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            context_json = json.dumps(context) if context else None
            cursor.execute("""
                INSERT INTO user_requests 
                (request_id, session_id, user_request, target_host, context)
                VALUES (?, ?, ?, ?, ?)
            """, (request_id, session_id, user_request, target_host, context_json))
    
    def log_proposed_command(
        self,
        command_id: str,
        request_id: str,
        command: str,
        risk_level: str,
        explanation: str = "",
    ) -> None:
        """Log a proposed command"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO proposed_commands
                (command_id, request_id, command, risk_level, explanation)
                VALUES (?, ?, ?, ?, ?)
            """, (command_id, request_id, command, risk_level, explanation))
    
    def log_approval(
        self,
        approval_id: str,
        command_id: str,
        user: str,
        approved: bool,
        reason: Optional[str] = None,
    ) -> None:
        """Log command approval/rejection"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO approvals
                (approval_id, command_id, user, approved, reason)
                VALUES (?, ?, ?, ?, ?)
            """, (approval_id, command_id, user, approved, reason))
    
    def log_execution(
        self,
        execution_id: str,
        session_id: str,
        command: str,
        host: str,
        user: str,
        command_id: Optional[str] = None,
    ) -> None:
        """Log a command execution"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO executions
                (execution_id, session_id, command_id, command, host, user)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (execution_id, session_id, command_id, command, host, user))
    
    def log_execution_result(
        self,
        execution_id: str,
        exit_code: int,
        duration_seconds: float,
    ) -> None:
        """Log execution result"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE executions
                SET exit_code = ?, duration_seconds = ?, end_time = CURRENT_TIMESTAMP
                WHERE execution_id = ?
            """, (exit_code, duration_seconds, execution_id))
    
    def log_output(self, output_id: str, execution_id: str, stdout: str, stderr: str) -> None:
        """Log command output"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Redact sensitive patterns
            stdout = self._redact_secrets(stdout)
            stderr = self._redact_secrets(stderr)
            cursor.execute("""
                INSERT INTO outputs (output_id, execution_id, stdout, stderr)
                VALUES (?, ?, ?, ?)
            """, (output_id, execution_id, stdout, stderr))
    
    def log_error(
        self,
        error_id: str,
        execution_id: str,
        error_message: str,
        error_type: str = "unknown",
    ) -> None:
        """Log an error"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO errors (error_id, execution_id, error_message, error_type)
                VALUES (?, ?, ?, ?)
            """, (error_id, execution_id, error_message, error_type))
    
    def get_session_history(self, session_id: str) -> list[dict]:
        """Get all commands in a session"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM executions WHERE session_id = ?
                ORDER BY start_time ASC
            """, (session_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_command_history(self, host: str, limit: int = 50) -> list[dict]:
        """Get command history for a host"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM executions WHERE host = ?
                ORDER BY start_time DESC, rowid DESC LIMIT ?
            """, (host, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_failed_commands(self, limit: int = 50) -> list[dict]:
        """Get failed command executions"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM executions WHERE exit_code != 0
                ORDER BY start_time DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def _redact_secrets(text: str) -> str:
        """Redact sensitive information from text"""
        import re
        
        # Redact common secret patterns
        text = re.sub(r"password[=:][\s]*[^\s]+", "password=***REDACTED***", text, flags=re.IGNORECASE)
        text = re.sub(r"api[_-]?key[=:][\s]*[^\s]+", "api_key=***REDACTED***", text, flags=re.IGNORECASE)
        text = re.sub(r"secret[=:][\s]*[^\s]+", "secret=***REDACTED***", text, flags=re.IGNORECASE)
        text = re.sub(r"token[=:][\s]*[^\s]+", "token=***REDACTED***", text, flags=re.IGNORECASE)
        text = re.sub(r"ssh[_-]?key[=:][\s]*[^\s]+", "ssh_key=***REDACTED***", text, flags=re.IGNORECASE)
        
        return text
