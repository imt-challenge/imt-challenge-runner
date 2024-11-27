#!/usr/bin/env python3
"""
Start an IMT Challenge based on a config file
"""

import argparse
import time

import docker

from instance import Participant


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
