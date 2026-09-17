"""Application bootstrap — explicit dependency injection, no globals.

Ownership (T0.7 decision): the Application creates, initializes, owns
and shuts down both the Runtime and the Persistence backend as
siblings — the Runtime never owns the database. ``create_application``
wires; ``run`` walks the deterministic startup/shutdown sequence:

```text
persistence.initialize → runtime.initialize → runtime.start
    → runtime.stop → runtime.shutdown → persistence.close
```

No AI, no network, no tools, no GUI — the skeleton only proves the
wiring works.

Failure rule: failures are logged with the safe error format and
re-raised unchanged — the runtime never pretends to be RUNNING, the
error keeps its classification, and initialized persistence is always
unwound (except when the runtime is still alive after a stop failure,
where closing underneath it would lie about the state).
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from chaos.cau_hinh.settings import ChaosSettings
from chaos.ha_tang.context import TraceContext, use_context
from chaos.ha_tang.contracts.errors import ConfigurationError
from chaos.ha_tang.logging import configure_logging, log_event, safe_summary
from chaos.ha_tang.persistence.sqlite_store import SqliteDatabase
from chaos.ha_tang.redaction import format_error, scrub_known_secrets
from chaos.ha_tang.runtime import Runtime

DATABASE_FILENAME = "chaos.db"


def _known_secrets(settings: ChaosSettings) -> list[str]:
    """Secret values owned by this configuration (memory only, never logged)."""
    if settings.ai.api_key is not None:
        return [settings.ai.api_key.expose()]
    return []


@dataclass(frozen=True)
class ApplicationContext:
    """Explicit dependency container. Frozen, constructed, never global.

    Holds only what orchestration needs: settings, the runtime, the
    configured logger and the owned persistence backend. Future
    dependencies arrive as new explicit fields — never a service
    locator, never a god object.
    """

    settings: ChaosSettings
    runtime: Runtime
    logger: logging.Logger
    persistence: SqliteDatabase


def _prepare_storage(path: Path) -> None:
    """Ensure the configured directory exists. The path itself is never
    logged — locations may contain sensitive segments (usernames)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError("cannot prepare storage location") from exc


class Application:
    """Owns one bootstrapped run from context to clean exit code."""

    def __init__(self, context: ApplicationContext) -> None:
        self._context = context

    @property
    def context(self) -> ApplicationContext:
        """The injected context (read-only reference)."""
        return self._context

    def run(self) -> int:
        """Full startup/shutdown walk. Returns the process exit code.

        Emits structured lifecycle events (``application.*`` and
        ``persistence.*``) under one per-run correlation context.
        """
        logger = self._context.logger
        persistence = self._context.persistence
        secrets = _known_secrets(self._context.settings)
        with use_context(TraceContext.new()):
            log_event(logger, "INFO", "application.started", safe_summary(self._context.settings))
            try:
                persistence.initialize()
            except Exception as exc:
                log_event(
                    logger,
                    "ERROR",
                    "persistence.initialization.failed",
                    {"error": scrub_known_secrets(format_error(exc), secrets)},
                )
                raise
            log_event(
                logger,
                "INFO",
                "persistence.initialized",
                {"schema_version": persistence.schema_version()},
            )
            try:
                self._context.runtime.initialize()
                self._context.runtime.start()
            except Exception as exc:
                try:
                    persistence.close()
                except Exception as close_exc:  # noqa: BLE001 — unwind must not mask `exc`; logged below
                    log_event(
                        logger,
                        "ERROR",
                        "persistence.shutdown.failed",
                        {"error": scrub_known_secrets(format_error(close_exc), secrets)},
                    )
                log_event(
                    logger,
                    "ERROR",
                    "application.start.failed",
                    {"error": scrub_known_secrets(format_error(exc), secrets)},
                )
                raise
            try:
                self._context.runtime.stop()
            except Exception as exc:
                log_event(
                    logger,
                    "ERROR",
                    "application.stop.failed",
                    {"error": scrub_known_secrets(format_error(exc), secrets)},
                )
                raise
            self.shutdown()
            log_event(logger, "INFO", "application.stopped")
            return 0

    def shutdown(self) -> None:
        """Stop the runtime, then close persistence (idempotent parts).

        Persistence closes even when the runtime halt fails (``finally``),
        so no engine dangles. The ``persistence.shutdown`` event fires only
        after the backend actually closed; a close failure is logged and
        propagated with the prior state left deterministic.
        """
        try:
            self._context.runtime.shutdown()
        finally:
            try:
                self._context.persistence.close()
            except Exception as exc:
                log_event(
                    self._context.logger,
                    "ERROR",
                    "persistence.shutdown.failed",
                    {
                        "error": scrub_known_secrets(
                            format_error(exc), _known_secrets(self._context.settings)
                        )
                    },
                )
                raise
        log_event(self._context.logger, "INFO", "persistence.shutdown")


def create_application(settings: ChaosSettings | None = None) -> Application:
    """Wire an application. ``None`` loads real process environment.

    Prepares the configured storage directory and builds (but does not
    open) the database — no connections at creation time.
    """
    resolved = ChaosSettings.from_env() if settings is None else settings
    logger = configure_logging(resolved.logging.level)
    db_path = Path(resolved.storage.data_dir) / DATABASE_FILENAME
    _prepare_storage(db_path)
    persistence = SqliteDatabase(db_path)
    return Application(
        ApplicationContext(
            settings=resolved, runtime=Runtime(), logger=logger, persistence=persistence
        )
    )


__all__ = ["DATABASE_FILENAME", "Application", "ApplicationContext", "create_application"]
