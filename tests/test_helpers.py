"""
Unit tests for services.helpers.
"""

import unittest
from contextlib import AbstractContextManager
from typing import Any
from unittest.mock import MagicMock, patch

import docker.errors

from services.helpers import (
    get_random_secret,
    get_random_string,
    pull_images,
    remove_network,
    sanitize_account_name,
    sanitize_docker_name,
    wait_until,
)


class FakeClock:
    """
    Drives monotonic time forward only when sleep() is called, so tests
    run without touching the real wall clock.
    """
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class RemoveNetworkTests(unittest.TestCase):
    def test_ignores_not_found(self) -> None:
        network = MagicMock()
        network.remove.side_effect = docker.errors.NotFound("gone")

        remove_network(network)

        network.remove.assert_called_once()

    def test_ignores_endpoint_conflict(self) -> None:
        network = MagicMock()
        network.remove.side_effect = docker.errors.APIError(
            "active endpoints",
            response=FakeResponse(409))

        remove_network(network)

        network.remove.assert_called_once()

    def test_reraises_unexpected_api_errors(self) -> None:
        network = MagicMock()
        network.remove.side_effect = docker.errors.APIError(
            "server exploded",
            response=FakeResponse(500))

        with self.assertRaises(docker.errors.APIError):
            remove_network(network)


class PullImagesTests(unittest.TestCase):
    def test_empty_image_list_does_not_create_executor(self) -> None:
        client = MagicMock()

        pull_images(client, [])

        client.images.pull.assert_not_called()

    def test_pulls_each_image(self) -> None:
        client = MagicMock()

        pull_images(client, ["one", "two"])

        client.images.pull.assert_any_call("one")
        client.images.pull.assert_any_call("two")
        self.assertEqual(client.images.pull.call_count, 2)


class GetRandomSecretTests(unittest.TestCase):
    def test_secrets_are_unique(self) -> None:
        secrets = [get_random_secret() for _ in range(10)]
        self.assertEqual(len(set(secrets)), 10)

    def test_default_length_meets_entropy_requirement(self) -> None:
        secret = get_random_secret()
        self.assertEqual(len(secret), 32)

    def test_custom_length(self) -> None:
        secret = get_random_secret(length=12)
        self.assertEqual(len(secret), 12)


class WaitUntilTests(unittest.TestCase):
    def _patch_clock(self, clock: FakeClock) -> AbstractContextManager[Any]:
        return patch.multiple(
            'services.helpers.time',
            monotonic=clock.monotonic,
            sleep=clock.sleep)

    def test_returns_immediately_when_predicate_true(self) -> None:
        clock = FakeClock()
        with self._patch_clock(clock):
            wait_until(lambda: True, timeout=10, interval=1)
        self.assertEqual(clock.sleeps, [])

    def test_retries_until_predicate_true(self) -> None:
        clock = FakeClock()
        attempts = {'n': 0}

        def predicate() -> bool:
            attempts['n'] += 1
            return attempts['n'] >= 3

        with self._patch_clock(clock):
            wait_until(predicate, timeout=10, interval=1)

        self.assertEqual(attempts['n'], 3)
        self.assertEqual(clock.sleeps, [1, 1])

    def test_raises_timeout_when_deadline_passes(self) -> None:
        clock = FakeClock()
        with self._patch_clock(clock):
            with self.assertRaises(TimeoutError) as cm:
                wait_until(
                    lambda: False,
                    timeout=5,
                    interval=1,
                    description="waiting for condition")
        # 5 sleeps of 1 second each exhaust the budget
        self.assertEqual(sum(clock.sleeps), 5)
        message = str(cm.exception)
        self.assertIn("5s", message)
        self.assertIn("waiting for condition", message)

    def test_final_sleep_clipped_to_remaining_budget(self) -> None:
        clock = FakeClock()
        with self._patch_clock(clock):
            with self.assertRaises(TimeoutError):
                wait_until(lambda: False, timeout=2.5, interval=1)
        self.assertEqual(clock.sleeps, [1, 1, 0.5])


class GetRandomStringTests(unittest.TestCase):
    def test_length_is_exact(self) -> None:
        for length in (1, 8, 32):
            self.assertEqual(len(get_random_string(length)), length)

    def test_only_lowercase_ascii(self) -> None:
        result = get_random_string(100)
        self.assertTrue(result.isalpha() and result.islower())

    def test_strings_are_unique(self) -> None:
        results = [get_random_string(16) for _ in range(10)]
        self.assertGreater(len(set(results)), 1)


class SanitizeAccountNameTests(unittest.TestCase):
    def test_lowercases_name(self) -> None:
        self.assertEqual(sanitize_account_name("MyTeam"), "myteam")

    def test_replaces_spaces_with_dots(self) -> None:
        self.assertEqual(sanitize_account_name("alpha bravo"), "alpha.bravo")

    def test_replaces_slashes_with_dots(self) -> None:
        self.assertEqual(sanitize_account_name("a/b"), "a.b")

    def test_combined_transforms(self) -> None:
        self.assertEqual(
            sanitize_account_name("Alpha Boat/Team"),
            "alpha.boat.team",
        )

    def test_already_clean(self) -> None:
        self.assertEqual(sanitize_account_name("clean"), "clean")


class SanitizeDockerNameTests(unittest.TestCase):
    def test_lowercases_name(self) -> None:
        self.assertEqual(sanitize_docker_name("TeamAlpha"), "teamalpha")

    def test_replaces_spaces_with_hyphens(self) -> None:
        self.assertEqual(sanitize_docker_name("Team Alpha"), "team-alpha")

    def test_replaces_invalid_punctuation(self) -> None:
        self.assertEqual(sanitize_docker_name("Team/Alpha#1"), "team-alpha-1")

    def test_preserves_valid_separators(self) -> None:
        self.assertEqual(sanitize_docker_name("team.alpha_1"), "team.alpha_1")

    def test_strips_leading_and_trailing_separators(self) -> None:
        self.assertEqual(
            sanitize_docker_name("...Team Alpha---"),
            "team-alpha")

    def test_rejects_empty_result(self) -> None:
        with self.assertRaises(ValueError):
            sanitize_docker_name("///")


if __name__ == '__main__':
    unittest.main()
