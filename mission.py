"""
Mission Config and Control
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from smm_client.organizations import SMMOrganization
from smm_client.types import SMMPoint
from services.helpers import get_random_string
from configloader import load_config

if TYPE_CHECKING:
    from services.smm import SMMServer
    from smm_client.connection import SMMConnection
    from smm_client.assets import SMMAssetType
    from smm_client.missions import SMMMission


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


def sanitize_account_name(account: str) -> str:
    """
    Turn an account name into something easier to use with smm
    - lowercase
    - no spaces
    - no slashes
    """
    return account.lower().replace(' ', '.').replace('/', '.')


class MissionRunnerParticipant:
    """
    Manage a Participant in a Mission
    This keeps track of state of a current participants mission
    """
    def __init__(self, parent: MissionRunner, smm: SMMServer) -> None:
        self.parent = parent
        self.smm = smm
        self.runner_password = get_random_string(12)
        self.asset_accounts = {}
        self.organization_admins = {}

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

    def create_mission(self) -> None:
        """
        Create the mission and populate it with the starting data
        """
        smm_imt_challenge = self.smm.get_web_connection(
            'imt-challenge',
            self.runner_password)
        mission = smm_imt_challenge.create_mission(
            self.parent.config['name'],
            self.parent.config['description'])
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
        participant.add_assets()
        self.participants.append(participant)

    def create_mission(self) -> None:
        """
        Create the mission in participants server(s)
        """
        for participant in self.participants:
            participant.create_mission()
