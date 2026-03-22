import importlib
import io
import sys

from loguru import logger as loguru_logger

logger_module = importlib.import_module("twscrape.logger")


def _reload_logger_module(monkeypatch, env_value: str | None = None):
    if env_value is None:
        monkeypatch.delenv("TWS_LOG_LEVEL", raising=False)
    else:
        monkeypatch.setenv("TWS_LOG_LEVEL", env_value)

    module = sys.modules.get("twscrape.logger", logger_module)
    return importlib.reload(module)


def teardown_function():
    module = sys.modules.get("twscrape.logger", logger_module)

    if module._SINK_ID is not None:
        loguru_logger.remove(module._SINK_ID)
        module._SINK_ID = None

    loguru_logger.disable("twscrape")


def test_import_does_not_register_sink(monkeypatch):
    handlers_before = tuple(loguru_logger._core.handlers)

    module = _reload_logger_module(monkeypatch)

    assert tuple(loguru_logger._core.handlers) == handlers_before
    assert module._SINK_ID is None


def test_invalid_env_defaults_to_info_without_registering_sink(monkeypatch):
    handlers_before = tuple(loguru_logger._core.handlers)

    module = _reload_logger_module(monkeypatch, "verbose")

    assert module._LOG_LEVEL == "INFO"
    assert tuple(loguru_logger._core.handlers) == handlers_before
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

    module.logger.warning("warning")
    module.logger.error("error")

    captured = capsys.readouterr()
    assert "warning" not in captured.err
    assert "error" in captured.err


def test_enable_logging_is_idempotent(monkeypatch, capsys):
    module = _reload_logger_module(monkeypatch)
    module.set_log_level("INFO")
    module.enable_logging()
    sink_id = module._SINK_ID

    module.enable_logging()
    module.logger.info("once")

    captured = capsys.readouterr()
    assert module._SINK_ID == sink_id
    assert captured.err.count("once") == 1
