"""
Unit tests for vehicle Docker resource handling.
"""

from unittest.mock import MagicMock

import docker
import pytest

from services.vehicle import Vehicle


def _smm_server() -> MagicMock:
    smm_server = MagicMock()
    smm_server.name = "team-alpha-smm"
    smm_server.internal_port = 8080
    smm_server.db_net = MagicMock()
    return smm_server


def test_vehicle_constructor_cleans_up_partial_create(
        mocker: MagicMock) -> None:
    docker_client = MagicMock()
    net = MagicMock()
    apm = MagicMock()
    mavproxy = MagicMock()

    docker_client.networks.get.side_effect = docker.errors.NotFound("missing")
    docker_client.networks.create.return_value = net
    docker_client.containers.create.side_effect = [apm, mavproxy]
    docker_client.images.pull.side_effect = docker.errors.APIError(
        "pull failed")
    mocker.patch(
        "services.vehicle.docker.from_env",
        return_value=docker_client)

    with pytest.raises(docker.errors.APIError):
        Vehicle("Alpha Boat", "Rover", _smm_server(), "user", "pass")

    apm.remove.assert_called_once_with(force=True)
    mavproxy.remove.assert_called_once_with(force=True)
    net.remove.assert_called_once_with()
