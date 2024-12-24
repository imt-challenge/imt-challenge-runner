#!/usr/bin/env python3
"""
Start an IMT Challenge based on a config file
"""

import argparse
import time

import docker

from instance import Participant
from mission import MissionRunner

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='imt-challenge-runner',
        description='Start and run an IMT challenge',
    )
    parser.add_argument(
        '-m',
        '--mission',
        required=True,
        help='load the mission description file')
    parser.add_argument(
        '-p',
        '--participant',
        required=True,
        action='append',
        help='load participant details from file')

    args = parser.parse_args()

    docker_client = docker.from_env()

    runner = MissionRunner(args.mission)

    participant_services = [
        Participant(participant) for participant in args.participant
    ]

    # Start all the services
    for participant in participant_services:
        participant.start(docker_client)

    # Add each participant to the runner
    for participant in participant_services:
        runner.add_participant(participant.smm)

    # Setup the participants in their server
    for participant in participant_services:
        participant.setup()

    runner.create_mission()

    for participant in participant_services:
        print(f"{participant.name}: http://localhost:{participant.smm.port}")

    print("Ready. Lets go")

    # Run the IMT Challenge
    start_time = time.time()
    while time.time() - start_time < 120:
        time.sleep(1)
        runner.time_tick()

    for participant in participant_services:
        participant.cleanup()
