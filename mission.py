"""
Mission Config and Control
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from smm_client.organizations import SMMOrganization
from services.helpers import get_random_string
from configloader import load_config

if TYPE_CHECKING:
    from services.smm import SMMServer
    from smm_client.connection import SMMConnection
    from smm_client.assets import SMMAssetType


def smm_get_or_create_asset_type(smm_conn: SMMConnection, asset_type: str) -> SMMAssetType:
    """
    Find the asset type object on the server
    Otherwise, create the asset type
    """
    asset_types = smm_conn.get_asset_types()
    for asset_type_obj in asset_types:
        if asset_type_obj.name == asset_type:
            return asset_type_obj
    return smm_conn.create_asset_type(asset_type, asset_type)


def smm_get_or_create_organization(smm_conn: SMMConnection, org_name: str) -> SMMOrganization:
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


class MissionRunner:
    """
    Runner for a Mission
    """
    def __init__(self, filename) -> None:
        self.runner_password = get_random_string(12)
        self.config = load_config(filename)
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

    def add_imt_login(self, smm: SMMServer) -> None:
        """
        Add the IMT monitor/manager account to this server
        """
        smm_admin = smm.get_web_connection()
        smm_admin.create_user('imt-challenge', self.runner_password)

    def add_assets(self, smm: SMMServer) -> None:
        """
        Add the known assets into the SMM instance
        """
        if 'assets' in self.config:
            smm_admin = smm.get_web_connection()
            smm_imt_challenge = smm.get_web_connection('imt-challenge', self.runner_password)
            for asset in self.config['assets']:
                asset_account = self.get_user_account_asset(asset['name'])
                asset_smm_account = smm_admin.create_user(asset_account['username'], asset_account['password'])
                asset_smm = smm_admin.create_asset(asset_smm_account, asset['name'], smm_get_or_create_asset_type(smm_admin, asset['type']))
                smm_asset = smm.get_web_connection(asset_account['username'], asset_account['password'])
                organization = smm_get_or_create_organization(smm_imt_challenge, asset['organization'])
                organization.add_member(asset_smm_account, role='A')
                org_asset_user = SMMOrganization(smm_asset, organization.id, organization.name)
                org_asset_user.add_asset(asset_smm)
                organization.add_member(asset_smm_account, role='M')
