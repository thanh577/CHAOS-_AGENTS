"""Persistence-boundary tests: stdlib sqlite3 only, no forbidden subsystems.

Database access in ``ha_tang/persistence`` is legitimate in T0.6 —
everything else on the forbidden list (network, subprocess, ORM,
AI/GUI/voice) must stay out. Imports remain stdlib-or-chaos.
"""

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

import chaos.ha_tang.persistence
import chaos.ha_tang.persistence.models
import chaos.ha_tang.persistence.repository
import chaos.ha_tang.persistence.sqlite_store

MODULE_FILES = [
    Path(chaos.ha_tang.persistence.__file__),
    Path(chaos.ha_tang.persistence.models.__file__),
    Path(chaos.ha_tang.persistence.repository.__file__),
    Path(chaos.ha_tang.persistence.sqlite_store.__file__),
]

FORBIDDEN = [
    r"\bsubprocess\b",
    r"\bsocket\b",
    r"\burllib\b",
    r"\bhttp\.client\b",
    r"\bhttp\.server\b",
    r"\bssl\b",
    r"\bos\.system\b",
    r"\bos\.popen\b",
    r"\bos\.exec\w*\b",
    r"\bos\.spawn\w*\b",
    r"\bshutil\b",
    # NOTE: `pathlib` is allowed here — Path only carries the configured
    # database location; the sole filesystem writer is sqlite3.connect
    # on that explicit path (reviewed, in-scope for T0.6).
    r"\bopen\s*\(",
    r"\b__import__\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bctypes\b",
    r"\bsqlalchemy\b",
    r"\balembic\b",
    r"\bpydantic\b",
    r"\bdotenv\b",
    r"\bplaywright\b",
    r"\bPySide6\b",
    r"\bopenai\b",
    r"\banthropic\b",
    r"\brequests\b",
    r"\bhttpx\b",
]


def _code_only(path: Path) -> str:
    tokens = tokenize.generate_tokens(io.StringIO(path.read_text(encoding="utf-8")).readline)
    kept = [t.string for t in tokens if t.type not in (tokenize.STRING, tokenize.COMMENT)]
    return "\n".join(kept)


def test_imports_are_stdlib_or_chaos_only():
    stdlib = set(sys.stdlib_module_names)
    violations = []
    for path in MODULE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                roots = [node.module.split(".")[0]] if node.module else []
            else:
                continue
            for root in roots:
                if root not in stdlib and root != "chaos":
                    violations.append(f"{path.name}: {root}")
    assert violations == []


def test_no_forbidden_subsystem_primitives():
    hits = []
    for path in MODULE_FILES:
        code = _code_only(path)
        for pattern in FORBIDDEN:
            if re.search(pattern, code):
                hits.append(f"{path.name}: {pattern}")
    assert hits == []


def test_sqlite_is_the_only_database_driver():
    import chaos.ha_tang.persistence.sqlite_store as store

    source = Path(store.__file__).read_text(encoding="utf-8")
    assert "import sqlite3" in source
    assert "sqlalchemy" not in source.lower()


def test_no_secret_shaped_literals_in_source():
    hits = []
    for path in MODULE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                lowered = node.value.lower()
                if "s3cr3t" in lowered or lowered.startswith("sk-"):
                    hits.append(f"{path.name}: {node.value!r}")
    assert hits == []
