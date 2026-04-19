"""
Postgres server
"""

from __future__ import annotations

import docker
import docker.errors
import docker.models.containers
import docker.models.networks

from .helpers import get_random_secret, remove_container, wait_until


class PostgresServer:
    """
    Run a postgresql server in a docker container
    This server will have the postgis extension
    """
    IMAGE = 'postgis/postgis:17-3.5'

    def __init__(self, name: str, network: docker.models.networks.Network, db_name: str, docker_client: docker.DockerClient) -> None:
        self.postgres_pass = get_random_secret(10)
        self.name = name
        self._db_name = db_name
        self.instance: docker.models.containers.Container | None
        self.instance = docker_client.containers.create(
            self.IMAGE,
            detach=True,
            name=name,
            environment=[
                f'POSTGRES_PASSWORD={self.postgres_pass}',
                f'POSTGRES_DB={self._db_name}'
            ]
        )
        network.connect(self.instance)

    def get_password(self) -> str:
        """
        Get the password for this postgres server
        """
        return self.postgres_pass

    def _is_ready(self) -> bool:
        """
        Return True once `pg_isready` reports the server accepts connections.
        """
        if self.instance is None:
            return False
        try:
            result = self.instance.exec_run(
                ['pg_isready', '-U', 'postgres', '-d', self._db_name])
        except docker.errors.APIError:
            return False
        return bool(result.exit_code == 0)

    def _wait_for_startup(self, timeout: float = 120.0) -> None:
        """
        Wait for the postgres server to accept connections.
        Raises TimeoutError if the server is not ready in time.
        """
        wait_until(
            self._is_ready,
            timeout=timeout,
            interval=1.0,
            description=f"postgres {self.name} to accept connections")

    def start(self) -> None:
        """
        Start this instance
        """
        assert self.instance is not None
        self.instance.start()
        self._wait_for_startup()

    def stop(self) -> None:
        """
        Stop this instance
        """
        if self.instance is None:
            return
        try:
            self.instance.stop()
        except (docker.errors.NotFound, docker.errors.APIError):
            pass

    def cleanup(self) -> None:
        """
        Cleanup from running this instance.
        Safe to call even if start() was never reached.
        """
        remove_container(self.instance)
        self.instance = None
