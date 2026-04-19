"""
Parser to load config for mission/participants
"""

import json
from typing import Any

import yaml

from configmodels import MissionConfig, ParticipantConfig


def load_config(filename: str) -> dict[str, Any]:
    """
    Load the config from a yaml or json file.
    Raises ValueError for unsupported extensions.
    """
    if filename.endswith('.yml') or filename.endswith('.yaml'):
        with open(filename, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    if filename.endswith('.json'):
        with open(filename, 'r', encoding='utf-8') as file:
            return json.load(file)
    raise ValueError(
        f"{filename}: unsupported file extension"
        " (expected .yml, .yaml, or .json)")


def load_mission_config(filename: str) -> MissionConfig:
    """
    Load and validate a mission config file.
    """
    data = load_config(filename)
    return MissionConfig.from_dict(data, filename)


def load_participant_config(filename: str) -> ParticipantConfig:
    """
    Load and validate a participant config file.
    """
    data = load_config(filename)
    return ParticipantConfig.from_dict(data, filename)
