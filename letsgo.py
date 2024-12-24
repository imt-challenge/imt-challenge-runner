#!/usr/bin/env python3
"""
Start an IMT Challenge based on a config file
"""

import argparse
import time

import docker

from instance import Participant
from mission import MissionRunner


def arg_is_positive(value) -> int:
    """
    Make sure the argument is positive
    """
    try:
        ivalue = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"{value} needs to be a positive integer") from exc
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"{value} must be positive")
    return ivalue


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='imt-challenge-runner',
        description='Start and run an IMT challenge',
    )
    parser.add_argument(
        '-t',
        '--time',
        default=120,
        type=arg_is_positive,
        help="Time IMT Challenge for (in seconds)"
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
    while time.time() - start_time < args.time:
        time.sleep(1)
        runner.time_tick()

    for participant in participant_services:
        participant.cleanup()
