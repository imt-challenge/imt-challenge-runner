#!/usr/bin/env python3
"""
Start an IMT Challenge based on a config file
"""

import argparse
import json
import time

import docker
import yaml

from services.smm import SMMServer


class Participant:
    """
    State for a participant
    """
    def __init__(self, filename: str) -> None:
        self.load_config(filename)

    def load_config(self, filename: str) -> bool:
        """
        Load in the participant config
        """
        config = None
        if filename.endswith('.yml') or filename.endswith('.yaml'):
            with open(filename, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
        elif filename.endswith('.json'):
            with open(filename, 'r', encoding='utf-8') as file:
                config = json.load(file)
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
            user = smm_admin.create_user(member['username'], member['password'])
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='imt-challenge-runner',
        description='Start and run an IMT challenge',
    )
    parser.add_argument('-m', '--mission', required=True, help='load the mission description file')
    parser.add_argument('-p', '--participant', required=True, action='append', help='load participant details from file')

    args = parser.parse_args()

    docker_client = docker.from_env()

    participant_services = []
    for participant in args.participant:
        participant_services.append(Participant(participant))

    # Start all the services
    for participant in participant_services:
        participant.start(docker_client)

    # Setup the participants in their server
    for participant in participant_services:
        participant.setup()

    # Run the IMT Challenge
    time.sleep(120)

    for participant in participant_services:
        participant.cleanup()
