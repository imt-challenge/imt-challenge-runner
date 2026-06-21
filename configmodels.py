"""
Typed dataclasses for mission and participant config files
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ConfigError(Exception):
    """Raised when a config file is missing required fields."""


def _require(
        data: dict[str, Any],
        key: str,
        filepath: str,
        prefix: str) -> Any:
    if key not in data or data[key] is None:
        field_path = f"{prefix}.{key}" if prefix else key
        raise ConfigError(f"{filepath}: {field_path} is required")
    return data[key]


@dataclass
class BaseLocation:
    """Latitude/longitude pair for an asset's base."""

    latitude: float
    longitude: float

    @classmethod
    def from_dict(
            cls,
            data: dict[str, Any],
            filepath: str,
            prefix: str) -> BaseLocation:
        """Build from a raw dict, raising ConfigError on missing fields."""
        lat = _require(data, 'latitude', filepath, prefix)
        lon = _require(data, 'longitude', filepath, prefix)
        return cls(latitude=float(lat), longitude=float(lon))


@dataclass
class AssetConfig:
    """Config for a single mission asset."""

    name: str
    type: str
    organization: str
    response_time_mins: int
    base_location: BaseLocation

    @classmethod
    def from_dict(
            cls,
            data: dict[str, Any],
            filepath: str,
            prefix: str) -> AssetConfig:
        """Build from a raw dict, raising ConfigError on missing fields."""
        name = _require(data, 'name', filepath, prefix)
        type_ = _require(data, 'type', filepath, prefix)
        org = _require(data, 'organization', filepath, prefix)
        rtm = _require(data, 'responseTimeMins', filepath, prefix)
        bl_data = _require(data, 'baseLocation', filepath, prefix)
        base_location = BaseLocation.from_dict(
            bl_data, filepath, f"{prefix}.baseLocation")
        return cls(
            name=str(name),
            type=str(type_),
            organization=str(org),
            response_time_mins=int(rtm),
            base_location=base_location,
        )


@dataclass
class POIConfig:
    """A point of interest in a mission."""

    name: str
    location: dict[str, float]


@dataclass
class MissionConfig:
    """Top-level mission configuration."""

    name: str
    description: str
    assets: list[AssetConfig]
    pois: list[POIConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any], filepath: str) -> MissionConfig:
        """Build from a raw dict, raising ConfigError on missing fields."""
        name = _require(data, 'name', filepath, '')
        description = _require(data, 'description', filepath, '')
        assets_data = _require(data, 'assets', filepath, '')
        assets = [
            AssetConfig.from_dict(a, filepath, f"assets[{i}]")
            for i, a in enumerate(assets_data)
        ]
        pois = []
        if data.get('POIs'):
            for poi in data['POIs']:
                if isinstance(poi, dict) \
                        and 'name' in poi and 'location' in poi:
                    pois.append(POIConfig(
                        name=poi['name'],
                        location=poi['location'],
                    ))
        return cls(
            name=str(name),
            description=str(description),
            assets=assets,
            pois=pois,
        )


@dataclass
class MemberConfig:
    """A single participant team member with login credentials."""

    username: str
    password: str

    @classmethod
    def from_dict(
            cls,
            data: dict[str, Any],
            filepath: str,
            prefix: str) -> MemberConfig:
        """Build from a raw dict, raising ConfigError on missing fields."""
        username = _require(data, 'username', filepath, prefix)
        password = _require(data, 'password', filepath, prefix)
        return cls(username=str(username), password=str(password))


@dataclass
class ParticipantConfig:
    """Top-level participant configuration."""

    name: str
    members: list[MemberConfig]

    @classmethod
    def from_dict(
            cls,
            data: dict[str, Any],
            filepath: str) -> ParticipantConfig:
        """Build from a raw dict, raising ConfigError on missing fields."""
        name = _require(data, 'name', filepath, '')
        members_data = _require(data, 'members', filepath, '')
        members = [
            MemberConfig.from_dict(m, filepath, f"members[{i}]")
            for i, m in enumerate(members_data)
        ]
        return cls(name=str(name), members=members)
