"""Structured-logging tests: levels, events, redaction, determinism."""

import logging

import pytest

from chaos.cau_hinh.settings import ChaosSettings
from chaos.ha_tang.context import TraceContext, clear_context, use_context
from chaos.ha_tang.contracts.errors import ConfigurationError
from chaos.ha_tang.logging import (
    LOG_FORMAT,
    STRUCTURED_FIELDS,
    configure_logging,
    log_event,
    resolve_level,
    safe_summary,
)


@pytest.fixture()
def records():
    logger = logging.getLogger("chaos-test-events")
    collected: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            collected.append(record)

    logger.addHandler(_Collector())
    logger.setLevel(logging.DEBUG)
    yield collected
    logger.handlers.clear()


def test_level_mapping_all_supported():
    assert resolve_level("debug") == logging.DEBUG
    assert resolve_level("INFO") == logging.INFO
    assert resolve_level("Warning") == logging.WARNING
    assert resolve_level("ERROR") == logging.ERROR
    assert resolve_level("critical") == logging.CRITICAL
    assert resolve_level(20) == logging.INFO
    with pytest.raises(ConfigurationError):
        resolve_level("VERBOSE")
    with pytest.raises(ConfigurationError):
        resolve_level(7)


def test_configuration_level_integration():
    logger = configure_logging(ChaosSettings.from_env({"CHAOS_LOG_LEVEL": "warning"}).logging.level)
    assert logger.level == logging.WARNING
    configure_logging("INFO")
    assert logger.level == logging.INFO


def test_no_duplicate_handlers():
    logger = logging.getLogger("chaos")
    before = len(logger.handlers)
    configure_logging("INFO")
    configure_logging("DEBUG")
    assert len(logger.handlers) == before
    assert logger.propagate is False


def test_log_format_deterministic():
    assert "%(asctime)s" in LOG_FORMAT
    assert "%(levelname)s" in LOG_FORMAT
    assert "%(message)s" in LOG_FORMAT
    assert STRUCTURED_FIELDS[0] == "event"


def test_log_event_shape_and_redaction(records):
    logger = logging.getLogger("chaos-test-events")
    context = TraceContext.new(session_id="s", task_id="t", tool_run_id="r")
    clear_context()
    with use_context(context):
        log_event(logger, "INFO", "tool.execution.started", {"api_key": "hidden", "tool": "echo"})
    assert len(records) == 1
    # logging unwraps a single-mapping arg into record.args itself.
    fields = records[0].args
    assert fields["event"] == "tool.execution.started"
    assert fields["correlation_id"] == context.correlation_id
    assert fields["session_id"] == "s"
    assert fields["task_id"] == "t"
    assert fields["tool_run_id"] == "r"
    assert fields["payload"] == {"api_key": "***", "tool": "echo"}
    assert "hidden" not in repr(fields)


def test_log_event_without_context(records):
    clear_context()
    logger = logging.getLogger("chaos-test-events")
    log_event(logger, logging.WARNING, "tool.execution.failed", None)
    fields = records[0].args  # logging unwraps a single-mapping arg itself
    assert fields["event"] == "tool.execution.failed"
    assert "correlation_id" not in fields
    assert "payload" not in fields


def test_safe_summary_still_secret_free():
    summary = safe_summary(ChaosSettings.from_env({"CHAOS_AI_API_KEY": "must-not-appear"}))
    assert "must-not-appear" not in repr(summary)
