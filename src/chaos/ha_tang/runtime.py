"""Runtime orchestrator — lifecycle plus future-service hooks.

The full agent loop (ARCHITECTURE layer 7, Milestone 15) will drive
these states later. In M0 the orchestrator only guarantees deterministic
transitions and a hook point where future subsystems (AI, tools,
memory, …) will attach — defaulting to zero services, so the skeleton
runs with no side effects.

Transition rule: hooks execute *before* the transition is recorded.
A failing hook leaves the state unchanged and the original exception
propagates with its error classification intact — the runtime never
claims a state it did not reach.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from enum import Enum

from chaos.ha_tang.contracts.errors import ValidationError


class RuntimeState(Enum):
    """Lifecycle of the application runtime. No FAILED state: M0 has
    no failure semantics beyond "transition refused, state unchanged"."""

    CREATED = "created"
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


class Service(ABC):
    """Empty hook for a future subsystem.

    Later milestones implement real services (AI adapter, tool router,
    …). The orchestrator calls ``startup`` in attach order during
    ``initialize`` and ``shutdown`` in reverse order during
    ``stop``/``shutdown``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable service identifier for logs and events."""
        raise NotImplementedError

    def startup(self) -> None:
        """Prepare the service. Default: nothing to do."""

    def shutdown(self) -> None:
        """Release the service. Default: nothing to do."""


class Runtime:
    """Minimal orchestrator. No threads, no loop, no side effects."""

    def __init__(self, services: Iterable[Service] = ()) -> None:
        self._state = RuntimeState.CREATED
        self._history: list[RuntimeState] = [self._state]
        self._services = tuple(services)

    @property
    def state(self) -> RuntimeState:
        """Current lifecycle state."""
        return self._state

    @property
    def history(self) -> tuple[RuntimeState, ...]:
        """States visited so far, in order."""
        return tuple(self._history)

    @property
    def services(self) -> tuple[Service, ...]:
        """Attached future-subsystem hooks (empty in M0)."""
        return self._services

    def _move(self, expected: RuntimeState, target: RuntimeState) -> None:
        if self._state is not expected:
            raise ValidationError(
                f"invalid runtime transition: {self._state.value} -> {target.value} "
                f"(expected {expected.value} -> {target.value})"
            )
        self._state = target
        self._history.append(target)

    def initialize(self) -> None:
        """CREATED -> INITIALIZED. Starts services first; a failing
        service aborts while still CREATED. No restart from STOPPED."""
        for service in self._services:
            service.startup()
        self._move(RuntimeState.CREATED, RuntimeState.INITIALIZED)

    def start(self) -> None:
        """INITIALIZED -> RUNNING. The future loop hooks in here."""
        self._move(RuntimeState.INITIALIZED, RuntimeState.RUNNING)

    def _halt(self) -> None:
        """Shared stop path: teardown hooks (reverse order), then
        STOPPING -> STOPPED. Called only from RUNNING or INITIALIZED,
        so a failing hook leaves a well-defined state behind."""
        for service in reversed(self._services):
            service.shutdown()
        self._move(self._state, RuntimeState.STOPPING)
        self._state = RuntimeState.STOPPED
        self._history.append(RuntimeState.STOPPED)

    def stop(self) -> None:
        """RUNNING -> STOPPING -> STOPPED. Idempotent from STOPPED
        (no-op, hooks not re-run)."""
        if self._state is RuntimeState.STOPPED:
            return
        if self._state is not RuntimeState.RUNNING:
            raise ValidationError(
                f"invalid runtime transition: {self._state.value} -> stopping "
                f"(expected {RuntimeState.RUNNING.value} -> stopping)"
            )
        self._halt()

    def shutdown(self) -> None:
        """Final halt from INITIALIZED, RUNNING (same path as
        ``stop``) or STOPPED (idempotent no-op). Never claims RUNNING
        without ``start``: INITIALIZED shuts down directly."""
        if self._state is RuntimeState.STOPPED:
            return
        if self._state not in (RuntimeState.INITIALIZED, RuntimeState.RUNNING):
            raise ValidationError(
                f"invalid runtime transition: {self._state.value} -> stopping "
                f"(expected initialized/running -> stopping)"
            )
        self._halt()


__all__ = ["Runtime", "RuntimeState", "Service"]
