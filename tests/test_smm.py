"""
Unit tests for SMM server startup helpers.
"""

from unittest.mock import MagicMock

import docker.errors
import pytest

from services.smm import SMMServer


def _server() -> SMMServer:
    server = object.__new__(SMMServer)
    server.name = "team-alpha-smm"
    server.internal_port = 8080
    server.instance = MagicMock()
    server.docker_client = MagicMock()
    return server


def test_ensure_image_available_checks_local_image() -> None:
    server = _server()

    server._ensure_image_available()

    server.docker_client.images.get.assert_called_once_with(SMMServer.IMAGE)


def test_ensure_image_available_raises_clear_error() -> None:
    server = _server()
    server.docker_client.images.get.side_effect = docker.errors.ImageNotFound(
        "missing")

    with pytest.raises(RuntimeError, match="must be pulled before starting"):
        server._ensure_image_available()


def test_resolve_host_port_reads_docker_binding() -> None:
    server = _server()
    server.instance.attrs = {
        "NetworkSettings": {
            "Ports": {
                "8080/tcp": [{"HostPort": "32768"}],
            },
        },
    }

    assert server._resolve_host_port() == 32768


def test_resolve_host_port_rejects_missing_binding() -> None:
    server = _server()
    server.instance.attrs = {
        "NetworkSettings": {
            "Ports": {},
        },
    }

    with pytest.raises(RuntimeError, match="no host port binding"):
        server._resolve_host_port()


def test_resolve_host_port_rejects_invalid_binding() -> None:
    server = _server()
    server.instance.attrs = {
        "NetworkSettings": {
            "Ports": {
                "8080/tcp": [{"HostPort": "not-a-port"}],
            },
        },
    }

    with pytest.raises(RuntimeError, match="is not an integer"):
        server._resolve_host_port()
