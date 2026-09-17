"""Application bootstrap — explicit dependency injection, no globals.

``create_application`` wires configuration into a frozen context;
``run`` walks the deterministic startup/shutdown sequence. No AI, no
network, no tools, no GUI — the skeleton only proves the wiring works.

Failure rule: a failed initialize/start is logged with the safe error
format and re-raised unchanged — the runtime never pretends to be
RUNNING and the error keeps its classification.
"""

import logging
from dataclasses import dataclass

from chaos.cau_hinh.settings import ChaosSettings
from chaos.ha_tang.context import TraceContext, use_context
from chaos.ha_tang.logging import configure_logging, log_event, safe_summary
from chaos.ha_tang.redaction import format_error
from chaos.ha_tang.runtime import Runtime


@dataclass(frozen=True)
class ApplicationContext:
    """Explicit dependency container. Frozen, constructed, never global.

    Holds only what orchestration needs today: settings, the runtime
    and the configured logger. Future dependencies arrive as new
    explicit fields — never a service locator.
    """

    settings: ChaosSettings
    runtime: Runtime
    logger: logging.Logger


class Application:
    """Owns one bootstrapped run from context to clean exit code."""

    def __init__(self, context: ApplicationContext) -> None:
        self._context = context

    @property
    def context(self) -> ApplicationContext:
        """The injected context (read-only reference)."""
        return self._context

    def run(self) -> int:
        """create -> initialize -> start -> running -> stop -> shutdown
        -> stopped. Returns the process exit code.

        Emits structured lifecycle events (``application.started`` /
        ``application.stopped`` / ``application.{start,stop}.failed``)
        under one per-run correlation context.
        """
        logger = self._context.logger
        with use_context(TraceContext.new()):
            log_event(logger, "INFO", "application.started", safe_summary(self._context.settings))
            try:
                self._context.runtime.initialize()
                self._context.runtime.start()
            except Exception as exc:
                log_event(logger, "ERROR", "application.start.failed", {"error": format_error(exc)})
                raise
            try:
                self._context.runtime.stop()
            except Exception as exc:
                log_event(logger, "ERROR", "application.stop.failed", {"error": format_error(exc)})
                raise
            self.shutdown()
            log_event(logger, "INFO", "application.stopped")
            return 0

    def shutdown(self) -> None:
        """Explicit final halt (idempotent via the runtime)."""
        self._context.runtime.shutdown()


def create_application(settings: ChaosSettings | None = None) -> Application:
    """Wire an application. ``None`` loads real process environment."""
    resolved = ChaosSettings.from_env() if settings is None else settings
    logger = configure_logging(resolved.logging.level)
    return Application(ApplicationContext(settings=resolved, runtime=Runtime(), logger=logger))


__all__ = ["Application", "ApplicationContext", "create_application"]
