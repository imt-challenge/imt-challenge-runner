#!/usr/bin/env python3
"""
Start an IMT Challenge based on a config file
"""

import argparse
import time

import docker

from services.smm import SMMServer


class Participant:
    """
    State for a participant
    """
    def __init__(self, filename: str) -> None:
        self.name = filename

    def start(self, docker_client) -> None:
        """
        Start the services for this participant
        """
        self.smm = SMMServer(f'{self.name}-smm', None, docker_client)
        self.smm.start()

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

    # Run the IMT Challenge
    time.sleep(120)

    for participant in participant_services:
        participant.cleanup()
