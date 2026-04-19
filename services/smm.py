"""
Manage Instances of Search Management Map
See: https://github.com/canterbury-air-patrol/search-management-map
"""

import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import docker
import docker.errors

from smm_client.connection import SMMConnection

from .postgres import PostgresServer
from .helpers import (
    get_random_secret,
    remove_container,
    remove_network,
    wait_until,
)


class SMMServer:
    # pylint: disable=R0902
    """
    A Search Management Map Instance
    """
    IMAGE = 'canterburyairpatrol/search-management-map:latest'

    def __init__(self, name: str, network, docker_client) -> None:
        self.port = None
        self.name = name
        self.external_network = network
        self.internal_port = 8080
        self.db_net = None
        self.postgres = None
        self.instance = None
        self.docker_client = docker_client
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
        self.admin_password = get_random_secret(10)

    def _is_web_ready(self) -> bool:
        """
        Return True when an HTTP GET to the server returns any 2xx/3xx.
        """
        try:
            with urllib.request.urlopen(
                    f'http://localhost:{self.port}/',
                    timeout=2) as resp:
                return 200 <= resp.status < 400
        except (urllib.error.URLError, OSError):
            return False

    def _wait_for_web_startup(self, timeout: float = 120.0) -> None:
        """
        Wait until the web server accepts HTTP requests.
        Raises TimeoutError if the server does not respond in time.
        """
        wait_until(
            self._is_web_ready,
            timeout=timeout,
            interval=1.0,
            description=f"SMM {self.name} web server on port {self.port}")

    def start(self) -> None:
        """
        Start this instance, and the related database server.
        Postgres startup and SMM image pull run concurrently.
        """
        with ThreadPoolExecutor(max_workers=2) as ex:
            pg_future = ex.submit(self.postgres.start)
            pull_future = ex.submit(self.docker_client.images.pull, self.IMAGE)
            pg_future.result()
            pull_future.result()
        self.instance = self.docker_client.containers.create(
            self.IMAGE,
            detach=True,
            name=self.name,
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
                f'{self.internal_port}/tcp': None,
            },
        )
        self.db_net.connect(self.instance)
        if self.external_network is not None:
            self.external_network.connect(self.instance)
        self.instance.start()
        self.instance.reload()
        port_bindings = self.instance.attrs['NetworkSettings']['Ports']
        self.port = int(
            port_bindings[f'{self.internal_port}/tcp'][0]['HostPort'])
        self._wait_for_web_startup()

    def stop(self) -> None:
        """
        Stop this instance, and the related database server
        """
        if self.instance is not None:
            try:
                self.instance.stop()
            except (docker.errors.NotFound, docker.errors.APIError):
                pass
        if self.postgres is not None:
            self.postgres.stop()

    def cleanup(self) -> None:
        """
        Cleanup from running this instance.
        Idempotent and tolerant of partial/failed starts.
        """
        remove_container(self.instance)
        self.instance = None
        if self.postgres is not None:
            self.postgres.cleanup()
            self.postgres = None
        remove_network(self.db_net)
        self.db_net = None

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
