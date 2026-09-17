"""Application bootstrap — explicit dependency injection, no globals.

``create_application`` wires configuration into a context; ``run``
walks the runtime lifecycle. No AI, no network, no tools, no GUI —
the skeleton only proves the wiring works.
"""

from dataclasses import dataclass

from chaos.cau_hinh.settings import ChaosSettings
from chaos.ha_tang.logging import configure_logging, safe_summary
from chaos.ha_tang.runtime import Runtime


@dataclass
class ApplicationContext:
    """Explicit dependency container. Constructed, never global."""

    settings: ChaosSettings
    runtime: Runtime


class Application:
    """Owns one bootstrapped run from context to clean exit code."""

    def __init__(self, context: ApplicationContext) -> None:
        self._context = context
        self._logger = configure_logging(context.settings.logging.level)

    @property
    def context(self) -> ApplicationContext:
        """The injected context (read-only reference)."""
        return self._context

    def run(self) -> int:
        """INITIALIZED -> RUNNING -> STOPPED. Returns process exit code."""
        self._logger.info("starting: %s", safe_summary(self._context.settings))
        self._context.runtime.initialize()
        self._context.runtime.start()
        self._context.runtime.stop()
        self._logger.info("stopped")
        return 0


def create_application(settings: ChaosSettings | None = None) -> Application:
    """Wire an application. ``None`` loads real process environment."""
    resolved = ChaosSettings.from_env() if settings is None else settings
    return Application(ApplicationContext(settings=resolved, runtime=Runtime()))


__all__ = ["Application", "ApplicationContext", "create_application"]
