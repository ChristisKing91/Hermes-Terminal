"""
Host registry and connection management
"""

import logging
from typing import Optional
from ..models import HostConfig, ConnectionType
from ..config import load_hosts_config
from ..shell.executor import LocalExecutor, RemoteExecutor

logger = logging.getLogger(__name__)


class HostRegistry:
    """Registry of managed hosts"""

    def __init__(self):
        self.hosts = load_hosts_config()
        self.connections: dict[str, LocalExecutor | RemoteExecutor] = {}

    def get_host(self, host_name: str) -> Optional[HostConfig]:
        """Get host configuration by name"""
        return self.hosts.get(host_name)

    def list_hosts(self) -> list[str]:
        """List all configured hosts"""
        return list(self.hosts.keys())

    def get_executor(self, host_name: str) -> Optional[LocalExecutor | RemoteExecutor]:
        """Get or create executor for a host"""
        if host_name in self.connections:
            return self.connections[host_name]

        host_config = self.get_host(host_name)
        if not host_config:
            logger.error(f"Host not found: {host_name}")
            return None

        try:
            if host_config.connection == ConnectionType.LOCAL:
                executor = LocalExecutor()
            else:
                executor = RemoteExecutor(
                    hostname=host_config.hostname or "",
                    username=host_config.user or "",
                    port=host_config.port,
                    ssh_key_path=host_config.ssh_key,
                    timeout=host_config.timeout,
                )
                if not executor.connect():
                    logger.error(f"Failed to connect to {host_name}")
                    return None

            self.connections[host_name] = executor
            return executor
        except Exception as e:
            logger.error(f"Failed to create executor for {host_name}: {e}")
            return None

    def close_connection(self, host_name: str) -> None:
        """Close connection to a host"""
        if host_name in self.connections:
            executor = self.connections[host_name]
            if isinstance(executor, RemoteExecutor):
                executor.disconnect()
            del self.connections[host_name]

    def close_all_connections(self) -> None:
        """Close all connections"""
        for host_name in list(self.connections.keys()):
            self.close_connection(host_name)
