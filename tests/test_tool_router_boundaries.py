"""ToolRouter boundary tests (T3.3, revised T4.3): dependency- and
scope-clean.

Mirrors test_brain_boundaries.py / test_event_bus_boundaries.py:
- imports are stdlib / chaos only (router.py legitimately imports the
  M2 EventBus and Event contract now that it is a real event
  producer, and — as of T4.3 — the M4 PermissionEngine *contract*
  now that permission checks are real; both are expected, not
  violations);
- router.py may depend on the PermissionEngine **abstraction**
  (``bao_mat.contracts.permission_engine``) only — never a concrete
  engine implementation (``bao_mat.engine``, ``bao_mat.recording``,
  ...). Which engine runs is a dependency-injection choice made by
  whoever constructs the router, never hardcoded here;
- no secret-shaped literals in source under test.
"""

import ast
import re
import sys
from pathlib import Path

import chaos.cong_cu.router

MODULE_FILES = [Path(chaos.cong_cu.router.__file__)]

# The one bao_mat dependency router.py is allowed: the abstract contract
# it needs to accept a PermissionEngine via DI (T4.3). Anything else under
# bao_mat is a concrete implementation and must never be imported here.
ALLOWED_BAO_MAT_IMPORT = "chaos.bao_mat.contracts.permission_engine"

# Bare names a concrete PermissionEngine implementation would introduce —
# router.py must only ever reference the abstraction, never one of these.
FORBIDDEN_CONCRETE_ENGINE_NAMES = ("StaticPermissionEngine", "RecordingPermissionEngine")

FORBIDDEN = [
    r"\bsubprocess\b",
    r"\bsocket\b",
    r"\burllib\.request\b",
    r"\bos\.system\b",
    r"\bshutil\b",
    r"\b__import__\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bctypes\b",
    r"\bsqlalchemy\b",
    r"\bpydantic\b",
    r"\bhttpx\b",
    r"\baiohttp\b",
    r"\bplaywright\b",
    r"\bbao_mat\.engine\b",
    r"\bbao_mat\.recording\b",
    r"\bStaticPermissionEngine\b",
    r"\bRecordingPermissionEngine\b",
]


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


def test_only_the_permission_engine_contract_is_a_legitimate_bao_mat_dependency():
    """AST-based (not text search): the only allowed ``bao_mat`` import
    is the abstract ``PermissionEngine`` contract; any other ``bao_mat``
    import (a concrete engine implementation) is a violation, and so is
    referencing a concrete engine's class name as a bare identifier."""
    hits = []
    for path in MODULE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "bao_mat" in alias.name and alias.name != ALLOWED_BAO_MAT_IMPORT:
                        hits.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "bao_mat" in module and module != ALLOWED_BAO_MAT_IMPORT:
                    hits.append(f"{path.name}: from {module} import ...")
            elif isinstance(node, ast.Name) and node.id in FORBIDDEN_CONCRETE_ENGINE_NAMES:
                hits.append(f"{path.name}: bare name {node.id!r}")
    assert hits == []


def test_no_forbidden_regex_patterns_outside_strings():
    """Regex scan over the raw source for anything :func:`ast.walk`
    can't see cleanly (module-level text like `subprocess.run(...)`
    hidden in a nested expression)."""
    hits = []
    for path in MODULE_FILES:
        code = path.read_text(encoding="utf-8")
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
