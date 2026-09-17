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
from chaos.ha_tang.logging import configure_logging, safe_summary
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
        -> stopped. Returns the process exit code."""
        logger = self._context.logger
        logger.info("starting: %s", safe_summary(self._context.settings))
        try:
            self._context.runtime.initialize()
            self._context.runtime.start()
        except Exception as exc:
            logger.error("startup failed: %s", format_error(exc))
            raise
        try:
            self._context.runtime.stop()
        except Exception as exc:
            logger.error("stop failed: %s", format_error(exc))
            raise
        self.shutdown()
        logger.info("stopped")
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
