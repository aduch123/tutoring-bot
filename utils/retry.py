"""Async retry decorator for Telegram API calls."""
import asyncio
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def async_retry(retries: int = 3, delay: float = 2.0, exceptions=(Exception,)):
    """
    Decorator that retries an async function on failure.
    Usage:
        @async_retry(retries=3, delay=2.0)
        async def my_function(): ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < retries:
                        logger.warning(
                            f"Attempt {attempt}/{retries} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {retries} attempts failed for {func.__name__}: {e}")
            raise last_exception
        return wrapper
    return decorator


async def safe_send(bot, chat_id: int, text: str, **kwargs) -> bool:
    """
    Safely send a message with retry logic.
    Returns True if sent successfully, False otherwise.
    """
    from telegram.error import TimedOut, NetworkError, RetryAfter
    for attempt in range(3):
        try:
            await bot.send_message(chat_id=chat_id, text=text, **kwargs)
            return True
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except (TimedOut, NetworkError) as e:
            if attempt < 2:
                await asyncio.sleep(2)
            else:
                logger.error(f"Failed to send message to {chat_id}: {e}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error sending to {chat_id}: {e}")
            return False
    return False
