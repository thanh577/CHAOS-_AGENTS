"""ToolRouter boundary tests (T3.3, revised T4.3 and T5.2): dependency-
and scope-clean.

Mirrors test_brain_boundaries.py / test_event_bus_boundaries.py:
- imports are stdlib / chaos only (router.py legitimately imports the
  M2 EventBus and Event contract now that it is a real event
  producer, the M4 PermissionEngine *contract* now that permission
  checks are real, and — as of T5.2 — the M5 Verifier *contract* now
  that verification is real; all expected, not violations);
- router.py may depend on the PermissionEngine/Verifier
  **abstractions** (``bao_mat.contracts.permission_engine``,
  ``kiem_tra.contracts.verifier``) only — never a concrete engine
  implementation (``bao_mat.engine``, ``bao_mat.recording``,
  ``kiem_tra.verifier``, ...). Which engine/verifier runs is a
  dependency-injection choice made by whoever constructs the router,
  never hardcoded here;
- no secret-shaped literals in source under test.
"""

import ast
import re
import sys
from pathlib import Path

import chaos.cong_cu.router

MODULE_FILES = [Path(chaos.cong_cu.router.__file__)]

# The only implementation-detail dependencies router.py is allowed: the
# abstract contracts it needs to accept a concrete PermissionEngine (M4)
# or Verifier (M5) via DI. Anything else under these subsystems is a
# concrete implementation and must never be imported here. Keyed by the
# substring that identifies a module as belonging to that subsystem.
ALLOWED_CONTRACT_IMPORTS = {
    "bao_mat": "chaos.bao_mat.contracts.permission_engine",
    "kiem_tra": "chaos.kiem_tra.contracts.verifier",
}

# Bare names a concrete PermissionEngine/Verifier implementation would
# introduce — router.py must only ever reference the abstractions.
FORBIDDEN_CONCRETE_ENGINE_NAMES = (
    "StaticPermissionEngine",
    "RecordingPermissionEngine",
    "ExecutionOutcomeVerifier",
)

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
    r"\bkiem_tra\.verifier\b",
    r"\bStaticPermissionEngine\b",
    r"\bRecordingPermissionEngine\b",
    r"\bExecutionOutcomeVerifier\b",
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


def test_only_the_permission_and_verifier_contracts_are_legitimate_dependencies():
    """AST-based (not text search): the only allowed ``bao_mat``/
    ``kiem_tra`` imports are the abstract ``PermissionEngine``/
    ``Verifier`` contracts; any other import from those subsystems (a
    concrete engine/verifier implementation) is a violation, and so is
    referencing one of their concrete class names as a bare identifier."""
    hits = []
    for path in MODULE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix, allowed in ALLOWED_CONTRACT_IMPORTS.items():
                        if prefix in alias.name and alias.name != allowed:
                            hits.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for prefix, allowed in ALLOWED_CONTRACT_IMPORTS.items():
                    if prefix in module and module != allowed:
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
