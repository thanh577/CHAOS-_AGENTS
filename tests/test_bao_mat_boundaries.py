"""bao_mat boundary tests (T4.4): Milestone 4 modules stay dependency-
and scope-clean.

Mirrors tests/test_event_bus_boundaries.py (M2):
- imports are stdlib / chaos only (no ORM/SDK literal in engine.py
  itself; recording.py may import chaos.ha_tang.persistence, which is
  a chaos import, not a direct sqlalchemy dependency of this module);
- no cong_cu reference anywhere in these modules — Permission Engine
  (ARCHITECTURE layer 6) must never depend on Tool Router (layer 5);
  that dependency runs the other way (cong_cu/router.py -> bao_mat's
  *contract*, T4.3);
- no secret-shaped literals in source under test.

Unlike test_event_bus_boundaries.py, ``PermissionEngine``/``bao_mat``
are not themselves forbidden strings here — these modules *are*
bao_mat, and ``PermissionEngine`` is the very base class they
implement, so forbidding those names would just flag their own
legitimate identity.
"""

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

import chaos.bao_mat.engine
import chaos.bao_mat.recording

MODULE_FILES = [
    Path(chaos.bao_mat.engine.__file__),
    Path(chaos.bao_mat.recording.__file__),
]

FORBIDDEN = [
    r"\bsubprocess\b",
    r"\bsocket\b",
    r"\burllib\.request\b",
    r"\bos\.system\b",
    r"\bshutil\b",
    r"\bopen\s*\(",
    r"\b__import__\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bctypes\b",
    r"\bsqlalchemy\b",
    r"\bpydantic\b",
    r"\bhttpx\b",
    r"\baiohttp\b",
    r"\bopenai\b",
    r"\banthropic\b",
    r"\bplaywright\b",
    r"\bcong_cu\b",
    r"\.env\b",
    r"\bdotenv\b",
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


def test_no_forbidden_subsystems_or_scope_leaks():
    hits = []
    for path in MODULE_FILES:
        code = _code_only(path)
        for pattern in FORBIDDEN:
            if re.search(pattern, code):
                hits.append(f"{path.name}: {pattern}")
    assert hits == []


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


def test_engine_does_not_import_persistence():
    """engine.py is the policy — it must stay independent of any
    particular audit sink (persistence, future ones, ...). Only
    recording.py is allowed to know about the persistence layer."""
    code = _code_only(Path(chaos.bao_mat.engine.__file__))
    assert "persistence" not in code
