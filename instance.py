"""
Classes to run an instance of IMT
"""

from __future__ import annotations

import logging

import docker

from configloader import load_participant_config
from configmodels import ConfigError, ParticipantConfig
from services.helpers import sanitize_docker_name
from services.smm import SMMServer

log = logging.getLogger(__name__)


class Participant:
    """
    State for a participant
    """
    def __init__(self, filename: str) -> None:
        config: ParticipantConfig = load_participant_config(filename)
        self.name = config.name
        try:
            self.service_name = sanitize_docker_name(config.name)
        except ValueError as exc:
            raise ConfigError(
                f"{filename}: participant name {config.name!r} cannot be "
                f"used as a Docker resource name: {exc}") from exc
        self.members = config.members
        self.smm: SMMServer | None = None

    def start(self, docker_client: docker.DockerClient) -> None:
        """
        Start the services for this participant
        """
        log.info("Starting participant %s", self.name)
        self.smm = SMMServer(f'{self.service_name}-smm', None, docker_client)
        self.smm.start()

    def setup(self) -> None:
        """
        Setup the participant(s) accounts in this instance
        """
        assert self.smm is not None
        log.info("Setting up accounts for participant %s", self.name)
        smm_admin = self.smm.get_web_connection()
        imt_org = smm_admin.create_organization('IMT')
        for member in self.members:
            user = smm_admin.create_user(
                member.username,
                member.password)
            imt_org.add_member(user)
            log.debug(
                "Created user %s for participant %s",
                member.username,
                self.name)

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
        log.debug("Cleaning up participant %s", self.name)
        if self.smm is not None:
            self.smm.cleanup()
            self.smm = None
        log.debug("Participant %s cleanup complete", self.name)
