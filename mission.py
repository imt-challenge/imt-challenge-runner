"""
Mission Config and Control
"""

from __future__ import annotations

import time

from typing import TYPE_CHECKING

from smm_client.missions import SMMMission
from smm_client.organizations import SMMOrganization
from smm_client.types import SMMPoint

from services.helpers import get_random_string, sanitize_account_name
from services.vehicle import Vehicle
from configloader import load_config

if TYPE_CHECKING:
    from services.smm import SMMServer
    from smm_client.connection import SMMConnection
    from smm_client.assets import SMMAssetType
    from smm_client.missions import SMMMissionOrganization

MAS_AWAITING_CREW = "Awaiting Crew"
MAS_AWAITING_TASKING = "Awaiting Tasking"
MAS_ENROUTE = "Enroute"
MAS_SEARCHING = "Searching"
MAS_INVESTIGATING = "Investigating"
MAS_RTB = "Returning to Base"
MISSION_ASSET_STATUSES = [
    MAS_AWAITING_CREW,
    MAS_AWAITING_TASKING,
    MAS_ENROUTE,
    MAS_SEARCHING,
    MAS_INVESTIGATING,
    MAS_RTB]


def smm_get_or_create_asset_type(
        smm_conn: SMMConnection,
        asset_type: str) -> SMMAssetType:
    """
    Find the asset type object on the server
    Otherwise, create the asset type
    """
    asset_types = smm_conn.get_asset_types()
    for asset_type_obj in asset_types:
        if asset_type_obj.name == asset_type:
            return asset_type_obj
    return smm_conn.create_asset_type(asset_type, asset_type)


def smm_get_or_create_organization(
        smm_conn: SMMConnection,
        org_name: str) -> SMMOrganization:
    """
    Find or create the organization on the server
    """
    organizations = smm_conn.get_organizations()
    for organization in organizations:
        if organization.name == org_name:
            return organization
    return smm_conn.create_organization(org_name)


class ParticipantAsset:
    # pylint: disable=R0902
    """
    Asset for a specific participant
    """
    def __init__(
        self,
        parent,
        config,
        smm_asset,
        smm_connection,
        smm_username,
        smm_password
    ) -> None:
        # pylint: disable=R0913,R0917
        self.parent = parent
        self.config = config
        self.smm_asset = smm_asset
        self.smm_connection = smm_connection
        self.smm_username = smm_username
        self.smm_password = smm_password
        self.added_time = None
        self.launch_time = None
        self.vehicle = None

    def add_to_mission(self) -> None:
        """
        Add this asset to a mission
        """
        mission = SMMMission(self.smm_connection, self.parent.mission_id, "")
        mission.add_asset(self.smm_asset)
        mission.set_asset_status(
            self.smm_asset,
            self.parent.mission_asset_statuses[MAS_AWAITING_CREW],
            "")
        self.added_time = time.time()

    def stop(self) -> None:
        """
        Stop/remove anything related to this asset
        """
        self.vehicle.stop()
        self.vehicle = None

    def time_tick(self):
        """
        Check if anything needs doing
        """
        if self.added_time is None:
            return
        if self.launch_time is None:
            now = time.time()
            if now - self.added_time \
               >= (int(self.config['responseTimeMins']) * 60):
                mission = SMMMission(
                    self.smm_connection,
                    self.parent.mission_id,
                    "")
                mission.set_asset_status(
                    self.smm_asset,
                    self.parent.mission_asset_statuses[MAS_AWAITING_TASKING],
                    "")
                self.launch_time = now
                self.vehicle = Vehicle(
                    self.smm_asset.name,
                    'Rover' if self.config['type'] == 'Boat'
                    else 'Plane' if self.config['type'] == 'Aircraft'
                    else 'Copter',
                    self.parent.smm,
                    self.smm_username,
                    self.smm_password,
                    lat=self.config['baseLocation']['latitude'],
                    lon=self.config['baseLocation']['longitude'])
                self.vehicle.start()


class MissionRunnerParticipant:
    # pylint: disable=R0902
    """
    Manage a Participant in a Mission
    This keeps track of state of a current participants mission
    """
    def __init__(self, parent: MissionRunner, smm: SMMServer) -> None:
        self.parent = parent
        self.smm = smm
        self.runner_password = get_random_string(12)
        self.mission_id = None
        self.mission_asset_statuses = {}
        self.assets: dict[str, ParticipantAsset] = {}
        self.asset_accounts = {}
        self.organization_admins = {}
        self.mission_org_list: list[SMMMissionOrganization] = []

    def get_user_account_asset(self, asset: str) -> object:
        """
        Get the user account for a specific asset
        """
        if asset not in self.asset_accounts:
            self.asset_accounts[asset] = {
                'username': sanitize_account_name(asset),
                'password': get_random_string(10)
            }
        return self.asset_accounts[asset]

    def add_imt_login(self) -> None:
        """
        Add the IMT monitor/manager account to this server
        """
        smm_admin = self.smm.get_web_connection()
        smm_admin.create_user('imt-challenge', self.runner_password)

    def setup_mission_asset_statuses(self):
        """
        Create the mission asset statuses in SMM
        """
        smm_admin = self.smm.get_web_connection()
        for status in MISSION_ASSET_STATUSES:
            self.mission_asset_statuses[status] = \
                smm_admin.get_or_create_mission_asset_status_value(
                    status,
                    status)

    def _setup_asset(
            self,
            asset,
            smm_admin,
            smm_imt_challenge) -> None:
        """
        Setup the asset in SMM
        """
        asset_account = self.get_user_account_asset(asset['name'])
        asset_smm_account = smm_admin.create_user(
            asset_account['username'],
            asset_account['password'])
        asset_smm = smm_admin.create_asset(
            asset_smm_account,
            asset['name'],
            smm_get_or_create_asset_type(smm_admin, asset['type']))
        smm_asset = self.smm.get_web_connection(
            asset_account['username'],
            asset_account['password'])
        organization = smm_get_or_create_organization(
            smm_imt_challenge,
            asset['organization'])
        organization.add_member(asset_smm_account, role='A')
        org_asset_user = SMMOrganization(
            smm_asset,
            organization.id,
            organization.name)
        org_asset_user.add_asset(asset_smm)
        organization.add_member(asset_smm_account, role='M')
        self.assets[asset['name']] = ParticipantAsset(
            self,
            asset,
            asset_smm,
            smm_asset,
            asset_account['username'],
            asset_account['password'])

    def add_assets(self) -> None:
        """
        Add the known assets into the SMM instance
        """
        if 'assets' in self.parent.config:
            smm_admin = self.smm.get_web_connection()
            smm_imt_challenge = self.smm.get_web_connection(
                'imt-challenge',
                self.runner_password)
            for asset in self.parent.config['assets']:
                self._setup_asset(asset, smm_admin, smm_imt_challenge)

    def _add_poi_to_mission(self, mission: SMMMission, poi: dict) -> bool:
        """
        Add a POI to a mission
        """
        location = poi.get('location')
        if not isinstance(location, dict):
            return False
        point = None
        if 'latitude' in location and 'longitude' in location:
            point = SMMPoint(location['latitude'], location['longitude'])
        name = poi.get('name')
        if point is not None and name is not None:
            mission.add_waypoint(point, name)
            return True
        return False

    def _get_smm_imt_challenge(self):
        """
        Get the SMMConnection for the imt challenge runner account
        """
        return self.smm.get_web_connection(
            'imt-challenge',
            self.runner_password)

    def create_mission(self) -> None:
        """
        Create the mission and populate it with the starting data
        """
        smm_imt_challenge = self._get_smm_imt_challenge()
        mission = smm_imt_challenge.create_mission(
            self.parent.config['name'],
            self.parent.config['description'])
        self.mission_id = mission.id
        if 'POIs' in self.parent.config:
            for poi in self.parent.config['POIs']:
                if not isinstance(poi, dict):
                    continue
                self._add_poi_to_mission(mission, poi)

        organisations = smm_imt_challenge.get_organizations(all_orgs=True)
        for organisation in organisations:
            if organisation.name == 'IMT':
                mission_org = mission.add_organization(organisation)
                # Make it so the IMT members can add other organizations
                # to the mission
                # Adding an organization is the trigger event to activate
                # the related asset(s)
                mission_org.set_can_add_organizations(value=True)

    def _get_mission(self, conn: SMMConnection) -> SMMMission:
        """
        Get the specific mission we are monitoring
        """
        return SMMMission(conn, self.mission_id, self.parent.config['name'])

    def check_added_organizations(self):
        """
        Check if any new organizations have been added to the mission
        """
        smm_imt_challenge = self._get_smm_imt_challenge()
        mission = self._get_mission(smm_imt_challenge)
        mission_orgs = mission.get_organizations()
        if len(mission_orgs) > len(self.mission_org_list):
            # New organization(s) have been added
            new_orgs = []
            for org in mission_orgs:
                found = any(
                    org.organization.name == org_have.organization.name
                    for org_have in self.mission_org_list
                )
                if not found:
                    new_orgs.append(org.organization)
            # Might need to add assets in response to this
            for asset in self.parent.config['assets']:
                if self.assets[asset['name']].added_time is None:
                    for org in new_orgs:
                        if asset['organization'] == org.name:
                            # Add this asset
                            self.assets[asset['name']].add_to_mission()

    def stop(self) -> None:
        """
        Stop/Cleanup anything related to this participant
        """
        for _, asset in self.assets.items():
            asset.stop()

    def time_tick(self) -> None:
        """
        Do the required per-tick checks
        """
        for _, asset in self.assets.items():
            asset.time_tick()


class MissionRunner:
    """
    Runner for a Mission
    """
    def __init__(self, filename) -> None:
        self.config = load_config(filename)
        self.participants = []

    def add_participant(self, smm: SMMServer) -> None:
        """
        Add a participant
        """
        participant = MissionRunnerParticipant(self, smm)
        participant.add_imt_login()
        participant.setup_mission_asset_statuses()
        participant.add_assets()
        self.participants.append(participant)

    def create_mission(self) -> None:
        """
        Create the mission in participants server(s)
        """
        for participant in self.participants:
            participant.create_mission()

    def stop(self) -> None:
        """
        Stop this mission
        """
        for participant in self.participants:
            participant.stop()

    def time_tick(self) -> None:
        """
        Increment the mission time
        """
        for participant in self.participants:
            participant.check_added_organizations()
            participant.time_tick()
