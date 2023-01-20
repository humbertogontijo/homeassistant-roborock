import asyncio
import functools


def get_running_loop_or_create_one():
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def run_in_executor():
    loop = get_running_loop_or_create_one()

    def decorator(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            return asyncio.run_coroutine_threadsafe(coro=func(*args, **kwargs), loop=loop)

        return wrapped

    return decorator
