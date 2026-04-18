"""
Postgres server
"""

import time

import docker
import docker.errors

from .helpers import get_random_string, remove_container


class PostgresServer:
    """
    Run a postgresql server in a docker container
    This server will have the postgis extension
    """
    def __init__(self, name, network, db_name, docker_client) -> None:
        self.postgres_pass = get_random_string(10)
        self.name = name
        self._db_name = db_name
        self.instance = None
        docker_client.images.pull('postgis/postgis:17-3.5')
        self.instance = docker_client.containers.create(
            'postgis/postgis:17-3.5',
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

    def _wait_for_startup(self) -> None:
        """
        Wait for the postgres server to start
        """
        for i in range(1, 120):
            logs = self.instance.logs().decode()
            if "ready for start up" in logs:
                return
            time.sleep(i)

    def start(self) -> None:
        """
        Start this instance
        """
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
