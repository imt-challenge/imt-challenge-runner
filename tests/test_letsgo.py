"""
Unit tests for challenge startup helpers.
"""

from unittest.mock import MagicMock

import docker
import pytest

import letsgo


def test_start_participant_closes_docker_client(
        mocker: MagicMock) -> None:
    docker_client = MagicMock()
    participant = MagicMock()
    participant.name = "Team Alpha"
    mocker.patch("letsgo.docker.from_env", return_value=docker_client)

    letsgo._start_participant(participant)

    participant.start.assert_called_once_with(docker_client)
    docker_client.close.assert_called_once_with()


def test_start_participant_closes_docker_client_after_failure(
        mocker: MagicMock) -> None:
    docker_client = MagicMock()
    participant = MagicMock()
    participant.name = "Team Alpha"
    participant.start.side_effect = RuntimeError("start failed")
    mocker.patch("letsgo.docker.from_env", return_value=docker_client)

    with pytest.raises(RuntimeError, match="start failed"):
        letsgo._start_participant(participant)

    docker_client.close.assert_called_once_with()


def test_start_participant_surfaces_docker_client_failure(
        mocker: MagicMock) -> None:
    participant = MagicMock()
    participant.name = "Team Alpha"
    mocker.patch(
        "letsgo.docker.from_env",
        side_effect=docker.errors.DockerException("daemon unavailable"))

    with pytest.raises(
            docker.errors.DockerException,
            match="daemon unavailable"):
        letsgo._start_participant(participant)

    participant.start.assert_not_called()
