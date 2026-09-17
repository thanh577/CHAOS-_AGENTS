"""kiem_tra boundary tests (T5.3): Milestone 5 module stays dependency-
and scope-clean.

Mirrors tests/test_bao_mat_boundaries.py (M4):
- imports are stdlib / chaos only (verifier.py legitimately imports the
  T0.2 ``ToolResult`` *contract* from ``cong_cu.contracts.tool`` to
  inspect a tool's outcome — a contract import, not a dependency on
  the Tool Router implementation);
- no ``cong_cu.router`` / ``ToolRouter`` reference anywhere in this
  module — the Verifier (ARCHITECTURE layer 7) must never depend on
  the Tool Router (layer 5); that dependency runs the other way
  (``cong_cu/router.py`` -> ``kiem_tra``'s *contract*, T5.2);
- no persistence or event-bus dependency — same reasoning as
  ``bao_mat/engine.py``: this is pure policy, and DATA_MODEL.md
  defines no ``verifications`` table for it to write to (the audit
  trail rides on ``ToolRouter``'s own ``EventBus`` publishing, not on
  anything this module does);
- no secret-shaped literals in source under test.

``Verifier``/``kiem_tra`` are not themselves forbidden strings here —
this module *is* kiem_tra, and ``Verifier`` is the very base class it
implements, so forbidding those names would just flag its own
legitimate identity (same exception as test_bao_mat_boundaries.py).
"""

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

import chaos.kiem_tra.verifier

MODULE_FILES = [Path(chaos.kiem_tra.verifier.__file__)]

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
    r"\bcong_cu\.router\b",
    r"\bToolRouter\b",
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


def test_verifier_does_not_import_persistence_or_event_bus():
    """verifier.py is pure policy — no dedicated ``verifications`` table
    exists to write to (DATA_MODEL.md), and publishing audit events is
    ``ToolRouter``'s job (T5.2), not this module's. Unlike
    ``bao_mat/recording.py``, there is no "recording" counterpart here
    at all — this is the one and only concrete Verifier in Milestone 5."""
    code = _code_only(Path(chaos.kiem_tra.verifier.__file__))
    assert "persistence" not in code
    assert "event_bus" not in code
    assert "EventBus" not in code


def test_verifier_only_depends_on_the_tool_result_contract_not_the_router():
    """The only ``cong_cu`` dependency allowed is the ``ToolResult``
    *contract* (``cong_cu.contracts.tool``) — never the router
    implementation. AST-based, mirrors the equivalent check in
    test_tool_router_boundaries.py for the opposite direction."""
    hits = []
    for path in MODULE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("chaos.cong_cu") and node.module != (
                    "chaos.cong_cu.contracts.tool"
                ):
                    hits.append(f"{path.name}: from {node.module} import ...")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("chaos.cong_cu") and alias.name != (
                        "chaos.cong_cu.contracts.tool"
                    ):
                        hits.append(f"{path.name}: import {alias.name}")
    assert hits == []
