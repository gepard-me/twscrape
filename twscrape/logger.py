import os
import sys
import time
from collections import OrderedDict
from collections.abc import Hashable
from typing import Literal

from loguru import logger

_TLOGLEVEL = Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_VALID_LOG_LEVELS = ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_LOGGER_NAME = "twscrape"


def _load_from_env() -> _TLOGLEVEL:
    env = os.getenv("TWS_LOG_LEVEL", "INFO").upper()
    if env not in _VALID_LOG_LEVELS:
        return "INFO"

    return env


_LOG_LEVEL: _TLOGLEVEL = _load_from_env()
_SINK_ID: int | None = None


def set_log_level(level: _TLOGLEVEL):
    global _LOG_LEVEL
    _LOG_LEVEL = level


def _filter(r):
    return r["name"].startswith(_LOGGER_NAME) and r["level"].no >= logger.level(_LOG_LEVEL).no


def enable_logging():
    global _SINK_ID

    logger.enable(_LOGGER_NAME)

    if _SINK_ID is None:
        _SINK_ID = logger.add(sys.stderr, filter=_filter)


logger.disable(_LOGGER_NAME)


class LogOnce:
    max_keys = 1024
    seen: OrderedDict[Hashable, None] = OrderedDict()
    pending: OrderedDict[Hashable, tuple[float, int]] = OrderedDict()

    @classmethod
    def once(cls, key: Hashable, level: _TLOGLEVEL, message: str) -> None:
        if key in cls.seen:
            cls.seen.move_to_end(key)
            return

        logger.log(level, message)
        cls.seen[key] = None
        if len(cls.seen) > cls.max_keys:
            cls.seen.popitem(last=False)

    @classmethod
    def throttled(cls, key: Hashable, level: _TLOGLEVEL, message: str, timeout: float = 60) -> None:
        now = time.monotonic()
        state = cls.pending.get(key)
        if state is None:
            logger.log(level, message)
            cls.pending[key] = (now, 0)
            if len(cls.pending) > cls.max_keys:
                cls.pending.popitem(last=False)
            return

        cls.pending.move_to_end(key)
        last_log, count = state
        count += 1
        if now - last_log < timeout:
            cls.pending[key] = (last_log, count)
            return

        logger.log(level, f"{message} ({count} occurrences since last log)")
        cls.pending[key] = (now, 0)
