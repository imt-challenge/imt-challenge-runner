"""
Manage Instances of Search Management Map
See: https://github.com/canterbury-air-patrol/search-management-map
"""
# pylint: disable=duplicate-code

from __future__ import annotations

import logging
import os
import urllib.error
import urllib.request

import docker
import docker.errors
import docker.models.containers
import docker.models.networks

from smm_client.connection import SMMConnection

from .helpers import (
    get_random_secret,
    remove_container,
    remove_network,
    wait_until,
)
from .postgres import PostgresServer

log = logging.getLogger(__name__)


class SMMServer:
    # pylint: disable=R0902
    """
    A Search Management Map Instance
    """
    IMAGE = 'canterburyairpatrol/search-management-map:latest'

    DEFAULT_ADMIN_EMAIL = 'imt-challenge@example.invalid'

    def __init__(
            self,
            name: str,
            network: docker.models.networks.Network | None,
            docker_client: docker.DockerClient,
            admin_email: str | None = None) -> None:
        self.port: int | None = None
        self.name = name
        self.external_network = network
        self.internal_port = 8080
        self.db_net: docker.models.networks.Network | None = None
        self.postgres: PostgresServer | None = None
        self.instance: docker.models.containers.Container | None = None
        self.docker_client = docker_client
        self.admin_email = (
            admin_email
            or os.environ.get('IMT_ADMIN_EMAIL')
            or self.DEFAULT_ADMIN_EMAIL
        )
        try:
            self.db_net = docker_client.networks.get(f'{name}-net')
        except docker.errors.NotFound:
            self.db_net = docker_client.networks.create(
                f'{name}-net',
                driver='bridge')
            log.debug("Created network %s-net", name)
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
                return bool(200 <= resp.status < 400)
        except (urllib.error.URLError, OSError):
            return False

    def _wait_for_web_startup(self, timeout: float = 120.0) -> None:
        """
        Wait until the web server accepts HTTP requests.
        Raises TimeoutError if the server does not respond in time.
        """
        log.debug(
            "Waiting for SMM %s web server on port %s",
            self.name,
            self.port)
        try:
            wait_until(
                self._is_web_ready,
                timeout=timeout,
                interval=1.0,
                description=f"SMM {self.name} web server on port {self.port}")
        except TimeoutError:
            if self.instance is not None:
                try:
                    raw = self.instance.logs(tail=200)
                    log.warning(
                        "SMM %s readiness timed out. Container logs:\n%s",
                        self.name, raw.decode(errors='replace'))
                except Exception:  # pylint: disable=broad-except
                    pass
            raise
        log.debug("SMM %s web server is ready", self.name)

    def start(self) -> None:
        """
        Start this instance, and the related database server.
        Images are pre-pulled by the caller; only postgres startup runs here.
        """
        assert self.postgres is not None
        assert self.db_net is not None
        log.info("Starting SMM %s", self.name)
        self.postgres.start()
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
                f'DJANGO_SUPERUSER_EMAIL={self.admin_email}',
            ],
            ports={
                f'{self.internal_port}/tcp': None,
            },
        )
        self.db_net.connect(self.instance)
        if self.external_network is not None:
            self.external_network.connect(self.instance)
        log.debug("Created SMM container %s", self.name)
        self.instance.start()
        self.instance.reload()
        port_bindings = self.instance.attrs['NetworkSettings']['Ports']
        self.port = int(
            port_bindings[f'{self.internal_port}/tcp'][0]['HostPort'])
        log.debug("SMM %s started on port %s", self.name, self.port)
        self._wait_for_web_startup()
        log.info("SMM %s ready on port %s", self.name, self.port)

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
        log.debug("Cleaning up SMM %s", self.name)
        remove_container(self.instance)
        self.instance = None
        if self.postgres is not None:
            self.postgres.cleanup()
            self.postgres = None
        remove_network(self.db_net)
        self.db_net = None
        log.debug("SMM %s cleanup complete", self.name)

    def get_web_connection(
            self,
            username: str = 'admin',
            password: str | None = None) -> SMMConnection:
        """
        Return an SMMConnection object connected to this server
        """
        actual_password = password if password is not None \
            else self.admin_password
        return SMMConnection(
            f'http://localhost:{self.port}',
            username,
            actual_password)
