"""RecordingPermissionEngine tests (T4.2): decisions -> permissions table."""

import asyncio

import pytest

from chaos.bao_mat.contracts.permission_engine import (
    PermissionDecision,
    PermissionEngine,
    PermissionRequest,
    PermissionVerdict,
)
from chaos.bao_mat.engine import StaticPermissionEngine
from chaos.bao_mat.recording import RecordingPermissionEngine
from chaos.ha_tang.contracts.common import PermissionClass
from chaos.ha_tang.contracts.errors import ExecutionError
from chaos.ha_tang.persistence.sqlite_store import SqliteDatabase, repositories


@pytest.fixture()
def database(tmp_path):
    db = SqliteDatabase(tmp_path / "test.db")
    db.initialize()
    yield db
    db.close()


@pytest.fixture()
def permission_repo(database):
    return repositories(database)["permissions"]


class _FixedEngine(PermissionEngine):
    def __init__(self, decision: PermissionDecision) -> None:
        self._decision = decision

    async def check(self, request: PermissionRequest) -> PermissionDecision:
        return self._decision


def _request(tool_name: str = "echo") -> PermissionRequest:
    return PermissionRequest(tool_name=tool_name, permission_class=PermissionClass.SAFE)


def test_returns_the_inner_decision_unchanged(permission_repo):
    decision = PermissionDecision(verdict=PermissionVerdict.ALLOW, reason="ok")
    engine = RecordingPermissionEngine(_FixedEngine(decision), permission_repo)
    out = asyncio.run(engine.check(_request()))
    assert out is decision


def test_persists_a_permission_row_matching_the_decision(permission_repo):
    engine = RecordingPermissionEngine(StaticPermissionEngine(), permission_repo)
    asyncio.run(engine.check(_request(tool_name="deploy")))
    rows = permission_repo.list()
    assert len(rows) == 1
    row = rows[0]
    assert row.tool_name == "deploy"
    assert row.verdict == "allow"
    assert row.reason


def test_confirm_and_block_verdicts_are_recorded_as_their_string_values(permission_repo):
    engine = RecordingPermissionEngine(StaticPermissionEngine(), permission_repo)
    asyncio.run(
        engine.check(PermissionRequest(tool_name="risky", permission_class=PermissionClass.CONFIRM))
    )
    asyncio.run(
        engine.check(PermissionRequest(tool_name="wipe", permission_class=PermissionClass.BLOCK))
    )
    verdicts = {row.tool_name: row.verdict for row in permission_repo.list()}
    assert verdicts == {"risky": "confirm", "wipe": "block"}


def test_each_check_gets_a_distinct_row(permission_repo):
    engine = RecordingPermissionEngine(StaticPermissionEngine(), permission_repo)
    asyncio.run(engine.check(_request()))
    asyncio.run(engine.check(_request()))
    rows = permission_repo.list()
    assert len({row.id for row in rows}) == 2


def test_direct_call_propagates_real_repository_errors(permission_repo, database):
    engine = RecordingPermissionEngine(StaticPermissionEngine(), permission_repo)
    database.close()
    with pytest.raises(ExecutionError):
        asyncio.run(engine.check(_request()))
