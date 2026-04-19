"""
Classes to run an instance of IMT
"""

from configloader import load_participant_config
from configmodels import ParticipantConfig
from services.smm import SMMServer


class Participant:
    """
    State for a participant
    """
    def __init__(self, filename: str) -> None:
        config: ParticipantConfig = load_participant_config(filename)
        self.name = config.name
        self.members = config.members
        self.smm = None

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
                member.username,
                member.password)
            imt_org.add_member(user)

    def stop(self) -> None:
        """
        Stop the services for this participant
        """
        if self.smm is not None:
            self.smm.stop()

    def cleanup(self) -> None:
        """
        Cleanup the services for this participant.
        Safe to call if start() was never reached or only partially succeeded.
        """
        if self.smm is not None:
            self.smm.cleanup()
            self.smm = None
