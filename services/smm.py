"""
Manage Instances of Search Management Map
See: https://github.com/canterbury-air-patrol/search-management-map
"""

import random
import time

import docker
import docker.errors

from smm_client.connection import SMMConnection

from .postgres import PostgresServer
from .helpers import get_random_string


class SMMServer:
    """
    A Search Management Map Instance
    """
    def __init__(self, name: str, network, docker_client) -> None:
        self.port = random.randint(20000, 65000)
        self.external_network = network
        self.internal_port = 8080
        try:
            self.db_net = docker_client.networks.get(f'{name}-net')
        except docker.errors.NotFound:
            self.db_net = docker_client.networks.create(
                f'{name}-net',
                driver='bridge')
        self.postgres = PostgresServer(
            f'{name}-db-server',
            self.db_net,
            'smm',
            docker_client)
        self.admin_password = get_random_string(10)
        docker_client.images.pull(
            'canterburyairpatrol/search-management-map:latest')
        self.instance = docker_client.containers.create(
            'canterburyairpatrol/search-management-map:latest',
            detach=True,
            name=name,
            environment=[
                f'DB_HOST={self.postgres.name}',
                f'DB_PASS={self.postgres.get_password()}',
                'DB_USER=postgres',
                'DB_NAME=smm',
                'DJANGO_SUPERUSER_USERNAME=admin',
                f'DJANGO_SUPERUSER_PASSWORD={self.admin_password}',
                'DJANGO_SUPERUSER_EMAIL=me@example.com',
            ],
            ports={
                f'{self.internal_port}/tcp': self.port,
            },
        )
        self.db_net.connect(self.instance)
        if self.external_network is not None:
            self.external_network.connect(self.instance)

    def _wait_for_web_startup(self) -> None:
        """
        Wait until the web server starts before continuing
        """
        for i in range(1, 120):
            logs = self.instance.logs().decode()
            if f"http://0.0.0.0:{self.internal_port}" in logs:
                return
            time.sleep(i)

    def start(self) -> None:
        """
        Start this instance, and the related database server
        """
        self.postgres.start()
        self.instance.start()
        self._wait_for_web_startup()

    def stop(self) -> None:
        """
        Stop this instance, and the related database server
        """
        self.instance.stop()
        self.postgres.stop()

    def cleanup(self) -> None:
        """
        Cleanup from running this instance
        """
        self.stop()
        self.instance.remove()
        self.postgres.cleanup()
        self.db_net.remove()

    def get_web_connection(
            self,
            username='admin',
            password=None) -> SMMConnection:
        """
        Return an SMMConnection object connected to this server
        """
        actual_password = password if password is not None \
            else self.admin_password
        return SMMConnection(
            f'http://localhost:{self.port}',
            username,
            actual_password)
