import os
import sys
from typing import Literal, cast

from loguru import logger

_TLOGLEVEL = Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_VALID_LOG_LEVELS = ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_LOGGER_NAME = "twscrape"


def _load_from_env() -> _TLOGLEVEL:
    env = os.getenv("TWS_LOG_LEVEL", "INFO").upper()
    if env not in _VALID_LOG_LEVELS:
        return "INFO"

    return cast(_TLOGLEVEL, env)


_LOG_LEVEL: _TLOGLEVEL = _load_from_env()
_SINK_ID: int | None = None


def set_log_level(level: _TLOGLEVEL):
    global _LOG_LEVEL
    _LOG_LEVEL = level


def _filter(r):
    return r["level"].no >= logger.level(_LOG_LEVEL).no


def enable_logging():
    global _SINK_ID

    logger.enable(_LOGGER_NAME)

    if _SINK_ID is None:
        _SINK_ID = logger.add(sys.stderr, filter=_filter)


logger.disable(_LOGGER_NAME)
