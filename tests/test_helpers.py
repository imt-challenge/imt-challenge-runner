"""
Unit tests for services.helpers.wait_until.
"""

import unittest
from unittest.mock import patch

from services.helpers import wait_until


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


class WaitUntilTests(unittest.TestCase):
    def _patch_clock(self, clock: FakeClock):
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


if __name__ == '__main__':
    unittest.main()
