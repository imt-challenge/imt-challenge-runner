"""
String helpers
"""

import random
import string

import docker
import docker.errors


def remove_container(container) -> None:
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


def remove_network(network) -> None:
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


def get_random_string(length) -> str:
    """
    Get a random string of ascii chargs
    """
    return ''.join(
        random.choice(string.ascii_lowercase) for _ in range(length))


def sanitize_account_name(account: str) -> str:
    """
    Turn an account name into something easier to use with smm
    - lowercase
    - no spaces
    - no slashes
    """
    return account.lower().replace(' ', '.').replace('/', '.')
