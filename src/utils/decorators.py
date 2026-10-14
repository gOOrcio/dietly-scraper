import logging
import functools
from typing import Callable

from src.utils.constants import USER_ID_NOT_SET_MSG


def require_user_id(func: Callable) -> Callable:
    """Decorator to ensure user_id is set before executing method."""

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not getattr(self, "user_id", None):
            logging.error(USER_ID_NOT_SET_MSG)
            return None
        return await func(self, *args, **kwargs)

    return wrapper


def log_api_call(operation: str):
    """Decorator to log API operations consistently."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                result = await func(self, *args, **kwargs)
                if result:
                    logging.info(f"{operation} successful")
                else:
                    logging.warning(f"{operation} failed")
                return result
            except Exception as e:
                logging.error(f"{operation} error: {e}")
                raise

        return wrapper

    return decorator
