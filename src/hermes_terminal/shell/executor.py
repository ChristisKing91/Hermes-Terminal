"""
Command execution - local and remote via SSH
"""

import subprocess
import logging
import time
from pathlib import Path
from typing import Optional, Tuple
import paramiko
from paramiko.ssh_exception import SSHException, AuthException

logger = logging.getLogger(__name__)


class LocalExecutor:
    """Execute commands locally"""

    def __init__(self, cwd: Optional[str] = None):
        self.cwd = Path(cwd or "~").expanduser()

    def execute(
        self, command: str, timeout: int = 30, shell: bool = True
    ) -> Tuple[int, str, str]:
        """
        Execute a local command.
        
        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        try:
            result = subprocess.run(
                command,
                cwd=self.cwd,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return 1, "", f"Execution error: {str(e)}"

    def change_directory(self, new_cwd: str) -> bool:
        """Change working directory"""
        try:
            path = Path(new_cwd).expanduser()
            if path.exists() and path.is_dir():
                self.cwd = path
                return True
            return False
        except Exception:
            return False

    def get_cwd(self) -> str:
        """Get current working directory"""
        return str(self.cwd)


class RemoteExecutor:
    """Execute commands remotely via SSH"""

    def __init__(
        self,
        hostname: str,
        username: str,
        port: int = 22,
        ssh_key_path: Optional[str] = None,
        timeout: int = 30,
    ):
        self.hostname = hostname
        self.username = username
        self.port = port
        self.ssh_key_path = ssh_key_path
        self.timeout = timeout
        self.client: Optional[paramiko.SSHClient] = None
        self.cwd = "~"

    def connect(self) -> bool:
        """Establish SSH connection"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if self.ssh_key_path:
                key_path = Path(self.ssh_key_path).expanduser()
                if key_path.exists():
                    self.client.connect(
                        self.hostname,
                        port=self.port,
                        username=self.username,
                        key_filename=str(key_path),
                        timeout=self.timeout,
                        look_for_keys=True,
                    )
                else:
                    logger.warning(f"SSH key not found: {key_path}")
                    self.client.connect(
                        self.hostname,
                        port=self.port,
                        username=self.username,
                        timeout=self.timeout,
                    )
            else:
                self.client.connect(
                    self.hostname,
                    port=self.port,
                    username=self.username,
                    timeout=self.timeout,
                )

            logger.info(f"Connected to {self.hostname} as {self.username}")
            return True
        except AuthException as e:
            logger.error(f"Authentication failed: {e}")
            return False
        except SSHException as e:
            logger.error(f"SSH connection failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def disconnect(self) -> None:
        """Close SSH connection"""
        if self.client:
            self.client.close()
            logger.info(f"Disconnected from {self.hostname}")

    def execute(
        self, command: str, timeout: Optional[int] = None
    ) -> Tuple[int, str, str]:
        """
        Execute a remote command.
        
        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if not self.client:
            return 1, "", "Not connected"

        try:
            # If command is cd, handle it locally
            if command.strip().startswith("cd "):
                parts = command.strip().split(None, 1)
                if len(parts) == 2:
                    new_cwd = parts[1]
                    # Validate the directory exists on remote
                    _, out, _ = self._execute_raw(f"test -d {new_cwd} && echo ok")
                    if "ok" in out:
                        self.cwd = new_cwd
                        return 0, f"Changed directory to {new_cwd}", ""
                    else:
                        return 1, "", f"Directory does not exist: {new_cwd}"
            
            # Execute with cwd context if needed
            full_command = f"cd {self.cwd} && {command}"
            exit_code, stdout, stderr = self._execute_raw(full_command, timeout)
            return exit_code, stdout, stderr
        except Exception as e:
            return 1, "", f"Execution error: {str(e)}"

    def _execute_raw(
        self, command: str, timeout: Optional[int] = None
    ) -> Tuple[int, str, str]:
        """Execute raw command without cwd context"""
        if not self.client:
            return 1, "", "Not connected"

        try:
            stdin, stdout, stderr = self.client.exec_command(
                command, timeout=timeout or self.timeout
            )
            exit_code = stdout.channel.recv_exit_status()
            out = stdout.read().decode()
            err = stderr.read().decode()
            return exit_code, out, err
        except Exception as e:
            return 1, "", f"Execution error: {str(e)}"

    def change_directory(self, new_cwd: str) -> bool:
        """Change working directory"""
        try:
            _, out, _ = self._execute_raw(f"test -d {new_cwd} && echo ok")
            if "ok" in out:
                self.cwd = new_cwd
                return True
            return False
        except Exception:
            return False

    def get_cwd(self) -> str:
        """Get current working directory"""
        return self.cwd
