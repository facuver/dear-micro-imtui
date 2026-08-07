import time

try:
    import machine
    _MP = True
except ImportError:
    _MP = False

import asyncio

async def sleep_ms(ms):
    """Cross-platform sleep."""
    if _MP:
        maybe_sleep_ms = getattr(asyncio, "sleep_ms", None)
        if maybe_sleep_ms is not None:
            await maybe_sleep_ms(ms)
            return
    await asyncio.sleep(ms / 1000.0)


def ticks_ms():
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms()
    return int(time.monotonic() * 1000)


def ticks_diff(new_ms, old_ms):
    if hasattr(time, "ticks_diff"):
        return time.ticks_diff(new_ms, old_ms)
    return new_ms - old_ms

