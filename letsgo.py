#!/usr/bin/env python3

import time

import docker

from services.smm import SMMServer


if __name__ == "__main__":
    docker_client = docker.from_env()
    smm = SMMServer('smm-test', None, docker_client)
    smm.start()
    time.sleep(120)
    smm.cleanup()
