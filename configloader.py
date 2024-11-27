"""
Parser to load config for mission/participants
"""

import json
import yaml


def load_config(filename) -> object:
    """
    Load the config from a yaml or json file
    """
    config = None
    if filename.endswith('.yml') or filename.endswith('.yaml'):
        with open(filename, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
    elif filename.endswith('.json'):
        with open(filename, 'r', encoding='utf-8') as file:
            config = json.load(file)
    return config
