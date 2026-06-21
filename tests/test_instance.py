"""
Unit tests for participant instance setup.
"""

from unittest.mock import MagicMock

import pytest

from configmodels import ConfigError, ParticipantConfig
from instance import Participant


def test_invalid_participant_docker_name_has_file_context(
        mocker: MagicMock) -> None:
    mocker.patch(
        "instance.load_participant_config",
        return_value=ParticipantConfig(name="///", members=[]))

    with pytest.raises(
            ConfigError,
            match=(
                "participant.yaml: participant name '///' cannot be used "
                "as a Docker resource name")):
        Participant("participant.yaml")
