"""
String helpers
"""

from __future__ import annotations

import secrets
import string
import time
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import docker
import docker.errors
import docker.models.containers
import docker.models.networks

_SECRET_ALPHABET = string.ascii_letters + string.digits + "-_"


def remove_container(
        container: docker.models.containers.Container | None) -> None:
    """
    Force-remove a docker container, tolerating a container that was
    never started or has already been removed.
    """
    if container is None:
        return
    try:
        container.remove(force=True)
    except docker.errors.NotFound:
        pass


def remove_network(network: docker.models.networks.Network | None) -> None:
    """
    Remove a docker network, tolerating networks that have already been
    removed or still have endpoints attached.
    """
    if network is None:
        return
    try:
        network.remove()
    except docker.errors.NotFound:
        pass
    except docker.errors.APIError as exc:
        print(f"Skipping removal of network {network.name}: {exc}")


def get_random_string(length: int) -> str:
    """
    Get a random string of ascii chars (non-secret, e.g. account names).
    """
    return ''.join(
        random.choice(string.ascii_lowercase) for _ in range(length))


def get_random_secret(length: int = 32) -> str:
    """
    Generate a cryptographically secure fixed-length URL-safe token.
    """
    return ''.join(secrets.choice(_SECRET_ALPHABET) for _ in range(length))


def wait_until(
        predicate: Callable[[], bool],
        timeout: float = 120.0,
        interval: float = 1.0,
        description: str = "condition") -> None:
    """
    Poll `predicate()` until it returns truthy, or raise TimeoutError
    once `timeout` seconds have elapsed. Sleeps `interval` seconds
    between polls.
    """
    deadline = time.monotonic() + timeout
    while True:
        if predicate():
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"Timed out after {timeout:.0f}s waiting for {description}")
        time.sleep(min(interval, remaining))


def pull_images(client: docker.DockerClient, images: list[str]) -> None:
    """
    Pull all images in parallel. Blocks until all pulls complete.
    """
    with ThreadPoolExecutor(max_workers=len(images)) as ex:
        futures = [ex.submit(client.images.pull, image) for image in images]
        for f in futures:
            f.result()


def sanitize_account_name(account: str) -> str:
    """
    Turn an account name into something easier to use with smm
    - lowercase
    - no spaces
    - no slashes
    """
    return account.lower().replace(' ', '.').replace('/', '.')
