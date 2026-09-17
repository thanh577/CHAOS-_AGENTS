"""MemoryStore contract tests: CRUD shapes on an in-memory double."""

import asyncio
import inspect

import pytest

from chaos.tri_nho.contracts.memory_store import MemoryQuery, MemoryRecord, MemoryStore


class DictMemory(MemoryStore):
    """In-memory test double — lives in tests, never in src."""

    def __init__(self) -> None:
        self._rows: dict[str, MemoryRecord] = {}

    async def store(self, record: MemoryRecord) -> MemoryRecord:
        self._rows[record.id] = record
        return record

    async def retrieve(self, query: MemoryQuery):
        rows = [r for r in self._rows.values() if query.scope in (None, r.scope)]
        return tuple(rows[: query.limit])

    async def update(self, record: MemoryRecord) -> MemoryRecord:
        self._rows[record.id] = record
        return record

    async def delete(self, record_id: str) -> bool:
        return self._rows.pop(record_id, None) is not None


def test_store_is_abstract():
    with pytest.raises(TypeError):
        MemoryStore()  # type: ignore[abstract]


def test_crud_surface_is_async():
    for method in ("store", "retrieve", "update", "delete"):
        assert inspect.iscoroutinefunction(getattr(MemoryStore, method))


def test_crud_shapes():
    store = DictMemory()
    rec = MemoryRecord(id="m1", content="remember this", scope="user")
    assert asyncio.run(store.store(rec)) == rec
    found = asyncio.run(store.retrieve(MemoryQuery(query="remember", limit=5)))
    assert found == (rec,)
    updated = MemoryRecord(id="m1", content="changed", scope="user")
    assert asyncio.run(store.update(updated)) == updated
    assert asyncio.run(store.retrieve(MemoryQuery(query="x", scope="other"))) == ()
    assert asyncio.run(store.delete("m1")) is True
    assert asyncio.run(store.delete("m1")) is False


def test_record_and_query_defaults():
    rec = MemoryRecord(id="m9", content="c")
    assert rec.scope == "default"
    assert rec.metadata == {}
    assert MemoryQuery(query="q").limit == 10
