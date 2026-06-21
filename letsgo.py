#!/usr/bin/env python3
"""
Start an IMT Challenge based on a config file
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import signal
import sys
import time
import types
from concurrent.futures import ThreadPoolExecutor

import docker

from configmodels import ConfigError
from instance import Participant
from mission import MissionRunner
from services.helpers import pull_images
from services.log import configure_logging
from services.postgres import PostgresServer
from services.smm import SMMServer

log = logging.getLogger(__name__)


def arg_is_positive(value: str) -> int:
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


def _install_signal_handlers() -> None:
    def _handle(signum: int, _frame: types.FrameType | None) -> None:
        raise KeyboardInterrupt(f"Received signal {signum}")
    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)


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
    parser.add_argument(
        '--keep',
        action='store_true',
        help='Skip teardown on exit so the operator can inspect state')
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable DEBUG logging')
    verbosity.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress INFO logging (WARNING and above only)')

    args = parser.parse_args()
    configure_logging(verbose=args.verbose, quiet=args.quiet)

    _install_signal_handlers()

    try:
        runner = MissionRunner(args.mission)
        participant_services = [
            Participant(participant) for participant in args.participant
        ]
    except (ConfigError, ValueError) as exc:
        log.error("%s", exc)
        sys.exit(1)

    docker_client = docker.from_env()

    n_workers = max(4, len(participant_services))
    pull_images(docker_client, [PostgresServer.IMAGE, SMMServer.IMAGE])

    with contextlib.ExitStack() as cleanup_stack:
        if not args.keep:
            # ExitStack unwinds in reverse, so register participant cleanup
            # first and runner.stop last — vehicle containers must go before
            # the SMM networks they are attached to.
            for participant in participant_services:
                cleanup_stack.callback(participant.cleanup)
            cleanup_stack.callback(runner.stop)

        # Start all participant services in parallel
        with ThreadPoolExecutor(max_workers=n_workers) as ex:
            futures = [
                ex.submit(p.start, docker_client) for p in participant_services
            ]
            for f in futures:
                f.result()

        # Add each participant to the runner (serial — touches shared state)
        for participant in participant_services:
            assert participant.smm is not None
            runner.add_participant(participant.smm)

        # Setup participant accounts in parallel
        with ThreadPoolExecutor(max_workers=n_workers) as ex:
            futures = [ex.submit(p.setup) for p in participant_services]
            for f in futures:
                f.result()

        runner.create_mission()

        for participant in participant_services:
            assert participant.smm is not None
            log.info(
                "%s: http://localhost:%s",
                participant.name,
                participant.smm.port)

        log.info("Ready. Lets go")

        # Run the IMT Challenge
        start_time = time.time()
        while time.time() - start_time < args.time:
            time.sleep(1)
            runner.time_tick()
