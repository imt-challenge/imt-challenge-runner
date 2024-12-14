"""
Classes to run an instance of IMT
"""

from configloader import load_config
from services.smm import SMMServer


class Participant:
    """
    State for a participant
    """
    def __init__(self, filename: str) -> None:
        self.load_config(filename)
        self.smm = None

    def load_config(self, filename: str) -> bool:
        """
        Load in the participant config
        """
        config = load_config(filename)
        if config is None:
            return False
        # These inputs should get checked
        self.name = config['name']
        self.members = config['members']
        return True

    def start(self, docker_client) -> None:
        """
        Start the services for this participant
        """
        self.smm = SMMServer(f'{self.name}-smm', None, docker_client)
        self.smm.start()

    def setup(self) -> None:
        """
        Setup the participant(s) accounts in this instance
        """
        smm_admin = self.smm.get_web_connection()
        imt_org = smm_admin.create_organization('IMT')
        for member in self.members:
            user = smm_admin.create_user(
                member['username'],
                member['password'])
            imt_org.add_member(user)

    def stop(self) -> None:
        """
        Stop the services for this participant
        """
        self.smm.stop()

    def cleanup(self) -> None:
        """
        Cleanup the services for this participant
        """
        self.smm.cleanup()
