"""
Unit tests for configloader.
"""

import json
import pathlib

import pytest
import yaml

from configloader import (
    load_config,
    load_mission_config,
    load_participant_config,
)
from configmodels import ConfigError


MINIMAL_ASSET: dict[str, object] = {
    "name": "Alpha Boat",
    "type": "Boat",
    "organization": "TeamAlpha",
    "responseTimeMins": 5,
    "baseLocation": {"latitude": -43.5, "longitude": 172.6},
}

MINIMAL_MISSION: dict[str, object] = {
    "name": "Test Mission",
    "description": "A test",
    "assets": [MINIMAL_ASSET],
}

MINIMAL_PARTICIPANT: dict[str, object] = {
    "name": "Team Alpha",
    "members": [{"username": "alice", "password": "secret"}],
}


def _write(tmp_path: pathlib.Path, name: str, data: object) -> str:
    p = tmp_path / name
    if name.endswith(".json"):
        p.write_text(json.dumps(data), encoding="utf-8")
    else:
        p.write_text(yaml.dump(data), encoding="utf-8")
    return str(p)


class TestLoadConfig:
    def test_loads_yaml(self, tmp_path: pathlib.Path) -> None:
        path = _write(tmp_path, "cfg.yaml", {"key": "value"})
        assert load_config(path) == {"key": "value"}

    def test_loads_yml(self, tmp_path: pathlib.Path) -> None:
        path = _write(tmp_path, "cfg.yml", {"a": 1})
        assert load_config(path) == {"a": 1}

    def test_loads_json(self, tmp_path: pathlib.Path) -> None:
        path = _write(tmp_path, "cfg.json", {"x": [1, 2]})
        assert load_config(path) == {"x": [1, 2]}

    def test_unknown_extension_raises(self, tmp_path: pathlib.Path) -> None:
        p = tmp_path / "cfg.toml"
        p.write_text("key = 'value'", encoding="utf-8")
        with pytest.raises(ValueError, match="unsupported file extension"):
            load_config(str(p))

    def test_missing_file_raises(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(str(tmp_path / "nonexistent.yaml"))

    def test_invalid_yaml_raises_parse_error(
            self,
            tmp_path: pathlib.Path) -> None:
        path = tmp_path / "invalid.yaml"
        path.write_text("key: [unclosed", encoding="utf-8")

        with pytest.raises(yaml.YAMLError):
            load_config(str(path))

    def test_invalid_yml_raises_parse_error(
            self,
            tmp_path: pathlib.Path) -> None:
        path = tmp_path / "invalid.yml"
        path.write_text("another: { malformed", encoding="utf-8")

        with pytest.raises(yaml.YAMLError):
            load_config(str(path))

    def test_invalid_json_raises_parse_error(
            self,
            tmp_path: pathlib.Path) -> None:
        path = tmp_path / "invalid.json"
        path.write_text('{"x": [1, 2] "y": 3}', encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            load_config(str(path))

    def test_empty_yaml_raises_config_error(
            self,
            tmp_path: pathlib.Path) -> None:
        path = tmp_path / "cfg.yaml"
        path.write_text("", encoding="utf-8")
        with pytest.raises(ConfigError, match="config root must be an object"):
            load_config(str(path))

    def test_scalar_yaml_raises_config_error(
            self,
            tmp_path: pathlib.Path) -> None:
        path = _write(tmp_path, "cfg.yaml", "not a mapping")
        with pytest.raises(ConfigError, match="config root must be an object"):
            load_config(path)

    def test_scalar_json_raises_config_error(
            self,
            tmp_path: pathlib.Path) -> None:
        path = _write(tmp_path, "cfg.json", ["not", "a", "mapping"])
        with pytest.raises(ConfigError, match="config root must be an object"):
            load_config(path)


class TestLoadMissionConfig:
    def test_valid_mission(self, tmp_path: pathlib.Path) -> None:
        path = _write(tmp_path, "mission.yaml", MINIMAL_MISSION)
        cfg = load_mission_config(path)
        assert cfg.name == "Test Mission"
        assert len(cfg.assets) == 1
        assert cfg.assets[0].name == "Alpha Boat"
        assert cfg.assets[0].response_time_mins == 5
        assert cfg.assets[0].base_location.latitude == pytest.approx(-43.5)

    def test_mission_with_pois(self, tmp_path: pathlib.Path) -> None:
        data = dict(MINIMAL_MISSION)
        data["POIs"] = [
            {
                "name": "Clue 1",
                "location": {"latitude": -43.6, "longitude": 172.7},
            }
        ]
        path = _write(tmp_path, "mission.yaml", data)
        cfg = load_mission_config(path)
        assert len(cfg.pois) == 1
        assert cfg.pois[0].name == "Clue 1"
        assert cfg.pois[0].location.latitude == pytest.approx(-43.6)
        assert cfg.pois[0].location.longitude == pytest.approx(172.7)

    def test_missing_name_raises(self, tmp_path: pathlib.Path) -> None:
        data = {k: v for k, v in MINIMAL_MISSION.items() if k != "name"}
        path = _write(tmp_path, "mission.yaml", data)
        with pytest.raises(ConfigError, match="name is required"):
            load_mission_config(path)

    def test_missing_assets_raises(self, tmp_path: pathlib.Path) -> None:
        data = {k: v for k, v in MINIMAL_MISSION.items() if k != "assets"}
        path = _write(tmp_path, "mission.yaml", data)
        with pytest.raises(ConfigError, match="assets is required"):
            load_mission_config(path)

    def test_assets_must_be_list(self, tmp_path: pathlib.Path) -> None:
        data = dict(MINIMAL_MISSION, assets={})
        path = _write(tmp_path, "mission.yaml", data)
        with pytest.raises(ConfigError, match="assets must be a list"):
            load_mission_config(path)

    def test_asset_must_be_object(self, tmp_path: pathlib.Path) -> None:
        data = dict(MINIMAL_MISSION, assets=["not an asset"])
        path = _write(tmp_path, "mission.yaml", data)
        with pytest.raises(
                ConfigError,
                match=r"assets\[0\] must be an object"):
            load_mission_config(path)

    def test_missing_asset_base_location_raises(
            self,
            tmp_path: pathlib.Path) -> None:
        asset = {
            k: v
            for k, v in MINIMAL_ASSET.items()
            if k != "baseLocation"
        }
        data = dict(MINIMAL_MISSION, assets=[asset])
        path = _write(tmp_path, "mission.yaml", data)
        with pytest.raises(ConfigError, match="baseLocation is required"):
            load_mission_config(path)

    def test_asset_response_time_must_be_integer(
            self,
            tmp_path: pathlib.Path) -> None:
        asset = dict(MINIMAL_ASSET)
        asset["responseTimeMins"] = "soon"
        data = dict(MINIMAL_MISSION, assets=[asset])
        path = _write(tmp_path, "mission.yaml", data)
        with pytest.raises(
                ConfigError,
                match=r"assets\[0\].responseTimeMins must be an integer"):
            load_mission_config(path)

    def test_asset_base_location_latitude_must_be_number(
            self,
            tmp_path: pathlib.Path) -> None:
        asset = dict(MINIMAL_ASSET)
        asset["baseLocation"] = {
            "latitude": "south",
            "longitude": 172.6,
        }
        data = dict(MINIMAL_MISSION, assets=[asset])
        path = _write(tmp_path, "mission.yaml", data)
        with pytest.raises(
                ConfigError,
                match=r"assets\[0\].baseLocation.latitude must be a number"):
            load_mission_config(path)

    def test_asset_response_time_rejects_boolean(
            self,
            tmp_path: pathlib.Path) -> None:
        asset = dict(MINIMAL_ASSET)
        asset["responseTimeMins"] = True
        data = dict(MINIMAL_MISSION, assets=[asset])
        path = _write(tmp_path, "mission.yaml", data)
        with pytest.raises(
                ConfigError,
                match=(
                    r"assets\[0\].responseTimeMins must be an integer, "
                    "not a boolean")):
            load_mission_config(path)

    def test_asset_base_location_latitude_rejects_boolean(
            self,
            tmp_path: pathlib.Path) -> None:
        asset = dict(MINIMAL_ASSET)
        asset["baseLocation"] = {
            "latitude": False,
            "longitude": 172.6,
        }
        data = dict(MINIMAL_MISSION, assets=[asset])
        path = _write(tmp_path, "mission.yaml", data)
        with pytest.raises(
                ConfigError,
                match=(
                    r"assets\[0\].baseLocation.latitude must be a number, "
                    "not a boolean")):
            load_mission_config(path)

    def test_pois_must_be_list(self, tmp_path: pathlib.Path) -> None:
        data = dict(MINIMAL_MISSION, POIs={})
        path = _write(tmp_path, "mission.yaml", data)
        with pytest.raises(ConfigError, match="POIs must be a list"):
            load_mission_config(path)

    def test_poi_must_be_object(self, tmp_path: pathlib.Path) -> None:
        data = dict(MINIMAL_MISSION, POIs=["not a poi"])
        path = _write(tmp_path, "mission.yaml", data)
        with pytest.raises(ConfigError, match=r"POIs\[0\] must be an object"):
            load_mission_config(path)

    def test_poi_location_is_required(self, tmp_path: pathlib.Path) -> None:
        data = dict(MINIMAL_MISSION, POIs=[{"name": "Clue 1"}])
        path = _write(tmp_path, "mission.yaml", data)
        with pytest.raises(
                ConfigError,
                match=r"POIs\[0\].location is required"):
            load_mission_config(path)

    def test_json_mission(self, tmp_path: pathlib.Path) -> None:
        path = _write(tmp_path, "mission.json", MINIMAL_MISSION)
        cfg = load_mission_config(path)
        assert cfg.name == "Test Mission"


class TestLoadParticipantConfig:
    def test_valid_participant(self, tmp_path: pathlib.Path) -> None:
        path = _write(tmp_path, "participant.yaml", MINIMAL_PARTICIPANT)
        cfg = load_participant_config(path)
        assert cfg.name == "Team Alpha"
        assert len(cfg.members) == 1
        assert cfg.members[0].username == "alice"

    def test_missing_members_raises(self, tmp_path: pathlib.Path) -> None:
        data = {"name": "Team Alpha"}
        path = _write(tmp_path, "participant.yaml", data)
        with pytest.raises(ConfigError, match="members is required"):
            load_participant_config(path)

    def test_members_must_be_list(self, tmp_path: pathlib.Path) -> None:
        data = {"name": "Team Alpha", "members": {}}
        path = _write(tmp_path, "participant.yaml", data)
        with pytest.raises(ConfigError, match="members must be a list"):
            load_participant_config(path)

    def test_member_must_be_object(self, tmp_path: pathlib.Path) -> None:
        data = {"name": "Team Alpha", "members": ["alice"]}
        path = _write(tmp_path, "participant.yaml", data)
        with pytest.raises(
                ConfigError,
                match=r"members\[0\] must be an object"):
            load_participant_config(path)

    def test_member_missing_password_raises(
            self,
            tmp_path: pathlib.Path) -> None:
        data = {"name": "Team Alpha", "members": [{"username": "alice"}]}
        path = _write(tmp_path, "participant.yaml", data)
        with pytest.raises(ConfigError, match="password is required"):
            load_participant_config(path)
