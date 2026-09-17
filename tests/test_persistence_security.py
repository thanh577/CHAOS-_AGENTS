"""Persistence security tests: parameterization, injection, secret safety."""

import pytest

from chaos.ha_tang.contracts.errors import ValidationError
from chaos.ha_tang.persistence.models import Message, Session
from chaos.ha_tang.persistence.sqlite_store import SqliteDatabase, repositories
from chaos.ha_tang.redaction import format_error


@pytest.fixture()
def repos(tmp_path):
    db = SqliteDatabase(tmp_path / "sec.db")
    db.initialize()
    yield repositories(db)
    db.close()


@pytest.mark.parametrize(
    "malicious",
    [
        "x' OR '1'='1",
        "'; DROP TABLE sessions;--",
        "' UNION SELECT * FROM settings;--",
        "a'; DELETE FROM messages;--",
    ],
)
def test_injection_input_stored_as_data(repos, malicious):
    repos["sessions"].create(Session(id="s1", title=malicious))
    assert repos["sessions"].get("s1").title == malicious
    # Tables and sibling rows survive verbatim hostile input.
    assert repos["sessions"].list()[0].id == "s1"
    repos["messages"].create(Message(id="m1", session_id="s1", role=malicious, content=malicious))
    fetched = repos["messages"].get("m1")
    assert (fetched.role, fetched.content) == (malicious, malicious)
    assert [row.id for row in repos["sessions"].list()] == ["s1"]


def test_injection_in_identifier_position_stays_inert(repos):
    hostile = "s1' OR '1'='1"
    assert repos["sessions"].get(hostile) is None
    assert repos["sessions"].delete(hostile) is False
    assert [row.id for row in repos["sessions"].list()] == []


def test_error_messages_carry_no_row_values(repos):
    secret_title = "s3cr3t-session-title"
    repos["sessions"].create(Session(id="dup", title=secret_title))
    with pytest.raises(ValidationError) as exc_info:
        repos["sessions"].create(Session(id="dup", title=secret_title))
    assert secret_title not in str(exc_info.value)
    assert secret_title not in format_error(exc_info.value)
