from __future__ import annotations

import functools
import logging
import math
import time

from custom_components.roborock.api.exceptions import RoborockBackoffException

DEFAULT_BACKOFF_MAX = 5 * 60

_LOGGER = logging.getLogger(__name__)


class BackOffStrategy:
    tries = 0
    last_execution: float | None

    def __init__(self, backoff_factor=1, backoff_max=DEFAULT_BACKOFF_MAX):
        self.backoff_factor = backoff_factor
        self.backoff_max = backoff_max
        self.last_execution = time.monotonic()

    def get_backoff_time(self):
        if self.tries > 0:
            backoff_value = self.backoff_factor * (2 ** (self.tries - 1))
            return min(self.backoff_max, backoff_value)
        return 0

    def get_last_success_time(self):
        return time.monotonic() - self.last_execution


def strategy_decorator(backoff_factor=1, backoff_max=DEFAULT_BACKOFF_MAX):
    self = BackOffStrategy(backoff_factor, backoff_max)

    def wrap_strategy(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            backoff_time = self.get_backoff_time()
            if self.get_last_success_time() >= backoff_time:
                try:
                    if backoff_time == self.backoff_max:
                        # Reset timer
                        self.last_execution = time.monotonic()
                    response = await func(*args, **kwargs)
                    self.tries = 0
                    self.last_execution = time.monotonic()
                    return response
                except Exception as e:
                    self.tries += 1
                    raise e
            raise RoborockBackoffException(
                f"Retries exceed. Try again in {math.ceil(self.get_backoff_time() - self.get_last_success_time())} seconds"
            )

        return wrapper

    return wrap_strategy
