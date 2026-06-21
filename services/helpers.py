"""
String helpers
"""

from __future__ import annotations

import logging
import random
import re
import secrets
import string
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import docker
import docker.errors
import docker.models.containers
import docker.models.networks

log = logging.getLogger(__name__)

_SECRET_ALPHABET = string.ascii_letters + string.digits + "-_"
_DOCKER_NAME_INVALID_CHARS = re.compile(r"[^a-z0-9_.-]+")


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
        log.warning("Skipping removal of network %s: %s", network.name, exc)


def log_container_logs_on_timeout(
        container: docker.models.containers.Container | None,
        name: str,
        kind: str,
        logger: logging.Logger) -> None:
    """
    Log recent container output after a readiness timeout.
    """
    if container is None:
        return
    try:
        raw = container.logs(tail=200)
        logger.warning(
            "%s %s readiness timed out. Container logs:\n%s",
            kind,
            name,
            raw.decode(errors='replace'))
    except Exception:  # pylint: disable=broad-except
        logger.debug(
            "Failed to retrieve logs for %s %s after readiness timeout",
            kind,
            name,
            exc_info=True)


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
    if not images:
        log.debug("No images to pull")
        return
    log.info("Pulling %d image(s): %s", len(images), ", ".join(images))
    with ThreadPoolExecutor(max_workers=len(images)) as ex:
        futures = [ex.submit(client.images.pull, image) for image in images]
        for f in futures:
            f.result()
    log.debug("All images pulled")


def sanitize_account_name(account: str) -> str:
    """
    Turn an account name into something easier to use with smm
    - lowercase
    - no spaces
    - no slashes
    """
    return account.lower().replace(' ', '.').replace('/', '.')


def sanitize_docker_name(name: str) -> str:
    """
    Convert a display name into a Docker container/network name fragment.
    """
    cleaned = _DOCKER_NAME_INVALID_CHARS.sub("-", name.lower())
    cleaned = cleaned.strip(".-_")
    if not cleaned:
        raise ValueError(
            f"{name!r} must contain at least one Docker-safe character")
    return cleaned
