"""Exponential backoff retry decorator for async functions."""

import asyncio
import functools
import logging

logger = logging.getLogger(__name__)


def retry_with_backoff(max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
    """Decorator: retry an async function with exponential backoff."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        logger.error(
                            "%s failed after %d attempts: %s", func.__name__, max_attempts, exc
                        )
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    # Special handling for 429 rate limits
                    status_code = getattr(exc, "status_code", None) or getattr(
                        getattr(exc, "response", None), "status_code", None
                    )
                    if status_code == 429:
                        delay = max(delay, 10.0)
                    logger.warning(
                        "%s attempt %d/%d failed (%s), retrying in %.1fs",
                        func.__name__,
                        attempt,
                        max_attempts,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator
