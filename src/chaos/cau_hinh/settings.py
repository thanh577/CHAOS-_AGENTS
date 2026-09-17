"""Centralized, type-safe application configuration (Milestone 0).

Sources: an explicit ``Mapping`` (tests/tools) or the process
environment (``CHAOS_``-prefixed variables). This module never reads
``.env`` files and never imports file/network/subprocess machinery —
loading stays pure and deterministic.

Secrets travel as :class:`Secret` and are redacted from ``repr``,
``str``, logs and error messages by construction.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from chaos.cau_hinh.secrets import Secret
from chaos.ha_tang.contracts.errors import ConfigurationError

ENVIRONMENTS = ("development", "testing", "production")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
MAX_TIMEOUT_SECONDS = 600.0

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _parse_bool(raw: str, *, field_name: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ConfigurationError(f"invalid boolean for {field_name}: {raw!r}")


@dataclass(frozen=True)
class AppSettings:
    """Identity of this run."""

    environment: str = "development"
    debug: bool = False

    def __post_init__(self) -> None:
        if self.environment not in ENVIRONMENTS:
            raise ConfigurationError(
                f"invalid environment: {self.environment!r} "
                f"(expected one of {', '.join(ENVIRONMENTS)})"
            )
        if self.debug and self.environment == "production":
            raise ConfigurationError("debug must not be enabled in production")


@dataclass(frozen=True)
class LoggingSettings:
    """Stdlib logging configuration (level only in M0)."""

    level: str = "INFO"

    def __post_init__(self) -> None:
        if self.level not in LOG_LEVELS:
            raise ConfigurationError(
                f"invalid log level: {self.level!r} (expected one of {', '.join(LOG_LEVELS)})"
            )


@dataclass(frozen=True)
class RuntimeSettings:
    """Bounds for future runtime operations. No execution here."""

    request_timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        timeout = self.request_timeout_seconds
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
            raise ConfigurationError(
                f"invalid request timeout: {timeout!r} (expected a number of seconds)"
            )
        if not 0 < timeout <= MAX_TIMEOUT_SECONDS:
            raise ConfigurationError(
                "invalid request timeout "
                f"(expected 0 < timeout <= {MAX_TIMEOUT_SECONDS:g}, got {timeout!r})"
            )


@dataclass(frozen=True)
class AISettings:
    """Placeholder for the future cloud-AI adapter (Milestone 1+).

    All fields optional outside production so CI and local runs work
    without credentials. ``api_key`` is a :class:`Secret` — redacted
    everywhere except :meth:`Secret.expose`.
    """

    provider_name: str | None = None
    model: str | None = None
    endpoint: str | None = None
    api_key: Secret | None = None


@dataclass(frozen=True)
class StorageSettings:
    """Storage *location* only. No database, no I/O in M0."""

    data_dir: str = "./data"

    def __post_init__(self) -> None:
        if not self.data_dir or not self.data_dir.strip():
            raise ConfigurationError("invalid storage location: data_dir must not be empty")


@dataclass(frozen=True)
class SecuritySettings:
    """Safety-boundary switches with secure defaults."""

    mask_secrets_in_logs: bool = True


@dataclass(frozen=True)
class ChaosSettings:
    """Root configuration object — the single type the bootstrap loads."""

    app: AppSettings = field(default_factory=AppSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    runtime: RuntimeSettings = field(default_factory=RuntimeSettings)
    ai: AISettings = field(default_factory=AISettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)

    @classmethod
    def defaults(cls) -> "ChaosSettings":
        """Deterministic development defaults (no environment read)."""
        return cls.from_env({})

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ChaosSettings":
        """Build settings from ``CHAOS_``-prefixed variables.

        ``env`` defaults to :data:`os.environ` but tests should pass an
        explicit mapping for determinism. ``.env`` files are never read.
        """
        source: Mapping[str, str] = os.environ if env is None else env

        def get(name: str) -> str | None:
            value = source.get(name)
            if value is None:
                return None
            text = value.strip()
            return text if text else None

        environment = (get("CHAOS_ENV") or "development").lower()
        debug = _parse_bool(get("CHAOS_DEBUG") or "false", field_name="CHAOS_DEBUG")
        log_level = (get("CHAOS_LOG_LEVEL") or "INFO").upper()
        data_dir = get("CHAOS_DATA_DIR") or "./data"
        mask_secrets = _parse_bool(
            get("CHAOS_MASK_SECRETS") or "true", field_name="CHAOS_MASK_SECRETS"
        )

        raw_timeout = get("CHAOS_REQUEST_TIMEOUT")
        try:
            timeout = 60.0 if raw_timeout is None else float(raw_timeout)
        except ValueError:
            raise ConfigurationError(
                f"invalid request timeout: {raw_timeout!r} (expected a number of seconds)"
            ) from None

        api_key_raw = get("CHAOS_AI_API_KEY")
        settings = cls(
            app=AppSettings(environment=environment, debug=debug),
            logging=LoggingSettings(level=log_level),
            runtime=RuntimeSettings(request_timeout_seconds=timeout),
            ai=AISettings(
                provider_name=get("CHAOS_AI_PROVIDER"),
                model=get("CHAOS_AI_MODEL"),
                endpoint=get("CHAOS_AI_ENDPOINT"),
                api_key=Secret(api_key_raw) if api_key_raw else None,
            ),
            storage=StorageSettings(data_dir=data_dir),
            security=SecuritySettings(mask_secrets_in_logs=mask_secrets),
        )
        settings.validate_for_environment()
        return settings

    def validate_for_environment(self) -> None:
        """Enforce required-vs-optional per environment.

        Production requires AI credentials (names only in the message —
        values, especially secrets, are never echoed).
        """
        if self.app.environment != "production":
            return
        missing = [
            name
            for name, present in (
                ("CHAOS_AI_PROVIDER", bool(self.ai.provider_name)),
                ("CHAOS_AI_MODEL", bool(self.ai.model)),
                ("CHAOS_AI_API_KEY", self.ai.api_key is not None),
            )
            if not present
        ]
        if missing:
            raise ConfigurationError(
                "missing required configuration for production: " + ", ".join(missing)
            )


__all__ = [
    "ENVIRONMENTS",
    "LOG_LEVELS",
    "MAX_TIMEOUT_SECONDS",
    "AISettings",
    "AppSettings",
    "ChaosSettings",
    "LoggingSettings",
    "RuntimeSettings",
    "SecuritySettings",
    "StorageSettings",
]
