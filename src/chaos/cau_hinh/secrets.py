"""Secret wrapper — values that must never appear in repr/logs/errors.

The raw value is only reachable via :meth:`Secret.expose`, which call
sites (future AI adapters) must use deliberately and never pass to
logging, exceptions or string formatting.
"""


class Secret:
    """An opaque string whose ``repr``/``str`` are always redacted."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("Secret value must be str")
        self._value = value

    def expose(self) -> str:
        """Return the raw value. Handle with care — never log it."""
        return self._value

    def __bool__(self) -> bool:
        return bool(self._value)

    def __repr__(self) -> str:
        return "Secret('***')"

    def __str__(self) -> str:
        return "***"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Secret):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)


__all__ = ["Secret"]
