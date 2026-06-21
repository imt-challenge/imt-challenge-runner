"""
Unit tests for mission.py ParticipantAsset and MissionRunnerParticipant logic.
"""

from unittest.mock import MagicMock

import pytest

from configmodels import AssetConfig, BaseLocation
from mission import MissionRunnerParticipant, ParticipantAsset


BASE_LOCATION = BaseLocation(latitude=-43.5, longitude=172.6)


def _asset_config(
    name: str = "Alpha Boat",
    org: str = "TeamAlpha",
    response_time_mins: int = 5,
) -> AssetConfig:
    return AssetConfig(
        name=name,
        type="Boat",
        organization=org,
        response_time_mins=response_time_mins,
        base_location=BASE_LOCATION,
    )


def _make_participant_asset(config: AssetConfig) -> ParticipantAsset:
    parent = MagicMock()
    return ParticipantAsset(
        parent=parent,
        config=config,
        smm_asset=MagicMock(),
        smm_connection=MagicMock(),
        smm_username="user",
        smm_password="pass",
    )


class TestParticipantAssetShouldLaunch:
    def test_not_added_returns_false(self) -> None:
        asset = _make_participant_asset(_asset_config())
        assert asset.added_time is None
        assert not asset.should_launch()

    def test_before_response_time_returns_false(
            self,
            mocker: MagicMock) -> None:
        asset = _make_participant_asset(_asset_config(response_time_mins=5))
        asset.added_time = 1000.0
        mocker.patch("mission.time.time", return_value=1000.0 + 4 * 60)
        assert not asset.should_launch()

    def test_at_response_time_returns_true(self, mocker: MagicMock) -> None:
        asset = _make_participant_asset(_asset_config(response_time_mins=5))
        asset.added_time = 1000.0
        mocker.patch("mission.time.time", return_value=1000.0 + 5 * 60)
        assert asset.should_launch()

    def test_after_response_time_returns_true(self, mocker: MagicMock) -> None:
        asset = _make_participant_asset(_asset_config(response_time_mins=2))
        asset.added_time = 0.0
        mocker.patch("mission.time.time", return_value=200.0)
        assert asset.should_launch()

    def test_already_launched_returns_false(self, mocker: MagicMock) -> None:
        asset = _make_participant_asset(_asset_config(response_time_mins=1))
        asset.added_time = 0.0
        asset.launch_time = 60.0
        mocker.patch("mission.time.time", return_value=999.0)
        assert not asset.should_launch()


def _make_mission_runner_participant(
    asset_configs: list[AssetConfig],
) -> MissionRunnerParticipant:
    mock_runner = MagicMock()
    mock_runner.config.assets = asset_configs
    mock_smm = MagicMock()
    participant = MissionRunnerParticipant(mock_runner, mock_smm)
    participant.mission_id = 42
    return participant


def _mock_mission_org(org_name: str) -> MagicMock:
    org = MagicMock()
    org.name = org_name
    mission_org = MagicMock()
    mission_org.organization = org
    return mission_org


class TestCheckAddedOrganizations:
    def test_matching_org_triggers_add_to_mission(
            self,
            mocker: MagicMock) -> None:
        config = _asset_config(org="TeamAlpha")
        participant = _make_mission_runner_participant([config])

        mock_pa = MagicMock(spec=ParticipantAsset)
        mock_pa.added_time = None
        participant.assets = {config.name: mock_pa}
        participant.mission_org_list = []

        mocker.patch.object(
            participant,
            "_get_smm_imt_challenge",
            return_value=MagicMock())
        mock_mission = MagicMock()
        mock_mission.get_organizations.return_value = [
            _mock_mission_org("TeamAlpha")
        ]
        mocker.patch.object(
            participant,
            "_get_mission",
            return_value=mock_mission)

        participant.check_added_organizations()

        mock_pa.add_to_mission.assert_called_once()

    def test_existing_org_is_not_reprocessed(
            self,
            mocker: MagicMock) -> None:
        config = _asset_config(org="TeamAlpha")
        participant = _make_mission_runner_participant([config])

        mock_pa = MagicMock(spec=ParticipantAsset)
        mock_pa.added_time = None
        participant.assets = {config.name: mock_pa}
        participant.mission_org_list = []

        mocker.patch.object(
            participant,
            "_get_smm_imt_challenge",
            return_value=MagicMock())
        mock_mission = MagicMock()
        team_alpha = _mock_mission_org("TeamAlpha")
        mock_mission.get_organizations.return_value = [team_alpha]
        mocker.patch.object(
            participant,
            "_get_mission",
            return_value=mock_mission)

        participant.check_added_organizations()
        participant.check_added_organizations()

        mock_pa.add_to_mission.assert_called_once()
        assert participant.mission_org_list == [team_alpha]

    def test_non_matching_org_does_not_trigger(
            self,
            mocker: MagicMock) -> None:
        config = _asset_config(org="TeamAlpha")
        participant = _make_mission_runner_participant([config])

        mock_pa = MagicMock(spec=ParticipantAsset)
        mock_pa.added_time = None
        participant.assets = {config.name: mock_pa}
        participant.mission_org_list = []

        mocker.patch.object(
            participant,
            "_get_smm_imt_challenge",
            return_value=MagicMock())
        mock_mission = MagicMock()
        mock_mission.get_organizations.return_value = [
            _mock_mission_org("TeamBeta")
        ]
        mocker.patch.object(
            participant,
            "_get_mission",
            return_value=mock_mission)

        participant.check_added_organizations()

        mock_pa.add_to_mission.assert_not_called()

    def test_already_added_asset_not_re_added(self, mocker: MagicMock) -> None:
        config = _asset_config(org="TeamAlpha")
        participant = _make_mission_runner_participant([config])

        mock_pa = MagicMock(spec=ParticipantAsset)
        mock_pa.added_time = 1000.0  # already added
        participant.assets = {config.name: mock_pa}
        participant.mission_org_list = []

        mocker.patch.object(
            participant,
            "_get_smm_imt_challenge",
            return_value=MagicMock())
        mock_mission = MagicMock()
        mock_mission.get_organizations.return_value = [
            _mock_mission_org("TeamAlpha")
        ]
        mocker.patch.object(
            participant,
            "_get_mission",
            return_value=mock_mission)

        participant.check_added_organizations()

        mock_pa.add_to_mission.assert_not_called()

    def test_only_new_orgs_trigger_add(self, mocker: MagicMock) -> None:
        config = _asset_config(org="TeamBeta")
        participant = _make_mission_runner_participant([config])

        mock_pa = MagicMock(spec=ParticipantAsset)
        mock_pa.added_time = None
        participant.assets = {config.name: mock_pa}

        # Org was already known
        existing_org_mo = _mock_mission_org("TeamAlpha")
        participant.mission_org_list = [existing_org_mo]

        mocker.patch.object(
            participant,
            "_get_smm_imt_challenge",
            return_value=MagicMock())
        mock_mission = MagicMock()
        new_org_mo = _mock_mission_org("TeamBeta")
        mock_mission.get_organizations.return_value = [
            existing_org_mo,
            new_org_mo,
        ]
        mocker.patch.object(
            participant,
            "_get_mission",
            return_value=mock_mission)

        participant.check_added_organizations()

        mock_pa.add_to_mission.assert_called_once()
        assert participant.mission_org_list == [existing_org_mo, new_org_mo]
