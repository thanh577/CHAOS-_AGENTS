"""Runtime skeleton — lifecycle states without an execution loop.

The full agent loop (ARCHITECTURE layer 7, Milestone 15) will drive
these states later. In M0 the runtime only tracks transitions so
bootstrap, tests and operators share one lifecycle vocabulary.
"""

from enum import Enum

from chaos.ha_tang.contracts.errors import ValidationError


class RuntimeState(Enum):
    """Lifecycle of the application runtime."""

    CREATED = "created"
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


class Runtime:
    """Minimal state machine. No threads, no loop, no side effects."""

    def __init__(self) -> None:
        self._state = RuntimeState.CREATED
        self._history: list[RuntimeState] = [self._state]

    @property
    def state(self) -> RuntimeState:
        """Current lifecycle state."""
        return self._state

    @property
    def history(self) -> tuple[RuntimeState, ...]:
        """States visited so far, in order."""
        return tuple(self._history)

    def _move(self, expected: RuntimeState, target: RuntimeState) -> None:
        if self._state is not expected:
            raise ValidationError(
                f"invalid runtime transition: {self._state.value} -> {target.value} "
                f"(expected {expected.value} -> {target.value})"
            )
        self._state = target
        self._history.append(target)

    def initialize(self) -> None:
        """CREATED -> INITIALIZED. Idempotent? No — single transition."""
        self._move(RuntimeState.CREATED, RuntimeState.INITIALIZED)

    def start(self) -> None:
        """INITIALIZED -> RUNNING. The future loop hooks in here."""
        self._move(RuntimeState.INITIALIZED, RuntimeState.RUNNING)

    def stop(self) -> None:
        """RUNNING -> STOPPING -> STOPPED. Recorded as two steps."""
        self._move(RuntimeState.RUNNING, RuntimeState.STOPPING)
        self._state = RuntimeState.STOPPED
        self._history.append(RuntimeState.STOPPED)


__all__ = ["Runtime", "RuntimeState"]
