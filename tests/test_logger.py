import importlib
import io
import sys
import time
from collections import OrderedDict
from typing import Any, cast

from loguru import logger as loguru_logger

logger_module = cast(Any, importlib.import_module("twscrape.logger"))


def setup_function():
    module = cast(Any, sys.modules.get("twscrape.logger", logger_module))
    if module._SINK_ID is not None:
        loguru_logger.remove(module._SINK_ID)
        module._SINK_ID = None

    loguru_logger.remove()
    loguru_logger.disable("twscrape")


def _reload_logger_module(monkeypatch, env_value: str | None = None) -> Any:
    if env_value is None:
        monkeypatch.delenv("TWS_LOG_LEVEL", raising=False)
    else:
        monkeypatch.setenv("TWS_LOG_LEVEL", env_value)

    module = cast(Any, sys.modules.get("twscrape.logger", logger_module))
    return importlib.reload(module)


def teardown_function():
    module = cast(Any, sys.modules.get("twscrape.logger", logger_module))

    if module._SINK_ID is not None:
        loguru_logger.remove(module._SINK_ID)
        module._SINK_ID = None

    loguru_logger.disable("twscrape")


def test_import_does_not_register_sink(monkeypatch):
    handlers_before = tuple(cast(Any, loguru_logger)._core.handlers)

    module = _reload_logger_module(monkeypatch)

    assert tuple(cast(Any, loguru_logger)._core.handlers) == handlers_before
    assert module._SINK_ID is None


def test_invalid_env_defaults_to_info_without_registering_sink(monkeypatch):
    handlers_before = tuple(cast(Any, loguru_logger)._core.handlers)

    module = _reload_logger_module(monkeypatch, "verbose")

    assert module._LOG_LEVEL == "INFO"
    assert tuple(cast(Any, loguru_logger)._core.handlers) == handlers_before
    assert module._SINK_ID is None


def test_logs_are_disabled_by_default_even_with_application_sink(monkeypatch):
    module = _reload_logger_module(monkeypatch)
    module.set_log_level("INFO")

    stream = io.StringIO()
    sink_id = loguru_logger.add(stream, format="{message}")
    try:
        exec('logger.info("hidden")', module.__dict__)
    finally:
        loguru_logger.remove(sink_id)

    assert stream.getvalue() == ""


def test_enable_logging_emits_to_stderr_and_honors_log_level(monkeypatch, capsys):
    module = _reload_logger_module(monkeypatch)
    module.set_log_level("ERROR")
    module.enable_logging()

    exec('logger.warning("warning")', module.__dict__)
    exec('logger.error("error")', module.__dict__)

    captured = capsys.readouterr()
    assert "warning" not in captured.err
    assert "error" in captured.err


def test_enable_logging_is_idempotent(monkeypatch, capsys):
    module = _reload_logger_module(monkeypatch)
    module.set_log_level("INFO")
    module.enable_logging()
    sink_id = module._SINK_ID

    module.enable_logging()
    exec('logger.info("once")', module.__dict__)

    captured = capsys.readouterr()
    assert sink_id == module._SINK_ID
    assert captured.err.count("once") == 1


def test_log_once_logs_each_key_once(monkeypatch):
    from twscrape.logger import LogOnce, logger

    logs = []
    monkeypatch.setattr(LogOnce, "seen", OrderedDict())
    monkeypatch.setattr(logger, "log", lambda level, message: logs.append((level, message)))

    LogOnce.once("a", "WARNING", "first")
    LogOnce.once("a", "WARNING", "duplicate")
    LogOnce.once("b", "WARNING", "second")

    assert logs == [("WARNING", "first"), ("WARNING", "second")]


def test_log_once_bounds_keys(monkeypatch):
    from twscrape.logger import LogOnce, logger

    logs = []
    monkeypatch.setattr(LogOnce, "max_keys", 2)
    monkeypatch.setattr(LogOnce, "seen", OrderedDict())
    monkeypatch.setattr(logger, "log", lambda level, message: logs.append((level, message)))

    for key in ("a", "b", "c", "a"):
        LogOnce.once(key, "WARNING", key)

    assert [message for _level, message in logs] == ["a", "b", "c", "a"]
    assert list(LogOnce.seen) == ["c", "a"]


def test_log_throttled_reports_and_resets_count(monkeypatch):
    from twscrape.logger import LogOnce, logger

    logs = []
    times = iter([0, 10, 20, 60, 70, 120])
    monkeypatch.setattr(LogOnce, "pending", OrderedDict())
    monkeypatch.setattr(time, "monotonic", lambda: next(times))
    monkeypatch.setattr(logger, "log", lambda level, message: logs.append((level, message)))

    for _ in range(6):
        LogOnce.throttled("a", "DEBUG", "message")

    assert logs == [
        ("DEBUG", "message"),
        ("DEBUG", "message (3 occurrences since last log)"),
        ("DEBUG", "message (2 occurrences since last log)"),
    ]


def test_log_throttled_bounds_independent_keys(monkeypatch):
    from twscrape.logger import LogOnce, logger

    logs = []
    monkeypatch.setattr(LogOnce, "max_keys", 2)
    monkeypatch.setattr(LogOnce, "pending", OrderedDict())
    monkeypatch.setattr(logger, "log", lambda level, message: logs.append((level, message)))

    for key in ("a", "b", "c"):
        LogOnce.throttled(key, "DEBUG", key)

    assert [message for _level, message in logs] == ["a", "b", "c"]
    assert list(LogOnce.pending) == ["b", "c"]
