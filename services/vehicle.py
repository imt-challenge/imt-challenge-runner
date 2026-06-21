"""
Vehicles
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import docker
import docker.errors
import docker.models.containers
import docker.models.networks

from services.helpers import (
    remove_container, remove_network, sanitize_docker_name)

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from services.smm import SMMServer


class Vehicle:
    """
    Generic Autopiloted vehicle
    """
    # pylint: disable=R0913,R0917
    def __init__(
        self,
        name: str,
        aircraft_type: str,
        smm_server: SMMServer,
        username: str,
        password: str,
        lat: float = -43.5,
        lon: float = 172.5,
    ) -> None:
        docker_client = docker.from_env()
        self.prefix_name = (
            f'{sanitize_docker_name(smm_server.name)}_'
            f'{sanitize_docker_name(name)}')
        self.net: docker.models.networks.Network | None = None
        self.apm: docker.models.containers.Container | None = None
        self.mavproxy: docker.models.containers.Container | None = None
        self.smm_mavlink: docker.models.containers.Container | None = None
        try:
            self._create(
                docker_client,
                name,
                aircraft_type,
                smm_server,
                username,
                password,
                lat,
                lon)
        except Exception:  # pylint: disable=broad-exception-caught
            try:
                self.stop()
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception(
                    "Error during vehicle cleanup after failed creation: %s",
                    name)
            raise
        finally:
            docker_client.close()
        log.debug("Created vehicle containers for %s", name)

    # pylint: disable=R0913,R0917
    def _create(
        self,
        docker_client: docker.DockerClient,
        name: str,
        aircraft_type: str,
        smm_server: SMMServer,
        username: str,
        password: str,
        lat: float,
        lon: float,
    ) -> None:
        """
        Create Docker resources for this vehicle.
        """
        try:
            self.net = docker_client.networks.get(f'ap_{self.prefix_name}-net')
        except docker.errors.NotFound:
            self.net = docker_client.networks.create(
                f'ap_{self.prefix_name}-net',
                driver='bridge')
        self.apm = docker_client.containers.create(
            f'sparlane/ardupilot-sitl:{aircraft_type}-latest',
            detach=True,
            name=f'{self.prefix_name}_sitl',
            environment=[
                f'LAT={lat}',
                f'LON={lon}',
                'BATT_CAPACITY=100000',
            ]
        )
        self.net.connect(self.apm)
        self.mavproxy = docker_client.containers.create(
            'sparlane/mavproxy:latest',
            detach=True,
            name=f'{self.prefix_name}_mavproxy',
            command=[
                "--non-interactive",
                "--master",
                f'tcp:{self.prefix_name}_sitl:5760',
                "--sitl",
                f'{self.prefix_name}_sitl:5501',
                "--out",
                "tcpin:0.0.0.0:5760",
                "--out",
                "tcpin:0.0.0.0:5761"
            ],
            environment=[
                f'LAT={lat}',
                f'LON={lon}',
                'BATT_CAPACITY=100000',
            ],
            ports={
                '5761/tcp': None,
            }
        )
        self.net.connect(self.mavproxy)
        docker_client.images.pull(
            'canterburyairpatrol/smm-mavlink:latest')
        self.smm_mavlink = docker_client.containers.create(
            'canterburyairpatrol/smm-mavlink:latest',
            command=[
                f"tcp:{self.prefix_name}_mavproxy:5760",
                f"http://{smm_server.name}:{smm_server.internal_port}",
                username,
                password,
                name
            ],
            detach=True,
            name=f'{self.prefix_name}_smm_mavlink')
        self.net.connect(self.smm_mavlink)
        if smm_server.db_net is None:
            raise RuntimeError(
                f"SMM server {smm_server.name} has no database network")
        smm_server.db_net.connect(self.smm_mavlink)

    def start(self) -> None:
        """
        Start the vehicle
        """
        log.info("Starting vehicle %s", self.prefix_name)
        if self.apm is None:
            raise RuntimeError(
                f"Vehicle {self.prefix_name} has no SITL container")
        if self.mavproxy is None:
            raise RuntimeError(
                f"Vehicle {self.prefix_name} has no MAVProxy container")
        if self.smm_mavlink is None:
            raise RuntimeError(
                f"Vehicle {self.prefix_name} has no SMM MAVLink container")
        self.apm.start()
        self.mavproxy.start()
        self.smm_mavlink.start()
        log.debug("Vehicle %s containers started", self.prefix_name)

    def stop(self) -> None:
        """
        Stop and tear down the vehicle containers and their private network.
        Idempotent and tolerant of containers that never started or are
        already removed.
        """
        for attr in ('smm_mavlink', 'mavproxy', 'apm'):
            remove_container(getattr(self, attr, None))
            setattr(self, attr, None)
        remove_network(self.net)
        self.net = None
