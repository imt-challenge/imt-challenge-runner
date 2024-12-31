"""
Vehicles
"""
import random

import docker

from services.helpers import sanitize_account_name


class Vehicle:
    """
    Generic Autopiloted vehicle
    """
    # pylint: disable=R0913,R0917
    def __init__(
        self,
        name,
        aircraft_type,
        smm_server,
        username,
        password,
        lat=-43.5,
        lon=172.5,
        idx=None
    ) -> None:
        docker_client = docker.from_env()
        self.prefix_name = f'{smm_server.name}_{sanitize_account_name(name)}'
        try:
            self.net = docker_client.networks.get(f'ap_{self.prefix_name}-net')
        except docker.errors.NotFound:
            self.net = docker_client.networks.create(
                f'ap_{self.prefix_name}-net',
                driver='bridge')
        self.ext_port = \
            31000 + idx if idx is not None else random.randint(30000, 31000)
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
                '5761/tcp': self.ext_port,
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
        smm_server.db_net.connect(self.smm_mavlink)

    def start(self):
        """
        Start the vehicle
        """
        self.apm.start()
        self.mavproxy.start()
        self.smm_mavlink.start()

    def stop(self):
        """
        Stop the vehicle
        """
        self.smm_mavlink.stop()
        self.mavproxy.stop()
        self.apm.stop()
