"""ToolRouter boundary tests (T3.3): dependency- and scope-clean.

Mirrors test_brain_boundaries.py / test_event_bus_boundaries.py:
- imports are stdlib / chaos only (router.py legitimately imports the
  M2 EventBus and Event contract now that it is a real event
  producer — that is expected, not a violation);
- no real bao_mat/PermissionEngine reference as *code* (the string
  "PermissionEngine" appears in human-readable error messages, which
  is fine — the check below is AST-based on names/imports, not text
  search, so message literals never trip it);
- no secret-shaped literals in source under test.
"""

import ast
import re
import sys
from pathlib import Path

import chaos.cong_cu.router

MODULE_FILES = [Path(chaos.cong_cu.router.__file__)]

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
    r"\bbao_mat\b",
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


def test_no_forbidden_subsystems_as_import_or_name():
    """AST-based (not text search): only real ``Import``/``Name`` nodes
    count, so an error-message string mentioning ``bao_mat`` in prose
    can never trip this — only an actual `import bao_mat` or a bare
    ``bao_mat``/``PermissionEngine`` identifier used as code would."""
    hits = []
    for path in MODULE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "bao_mat" in alias.name:
                        hits.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if "bao_mat" in (node.module or ""):
                    hits.append(f"{path.name}: from {node.module} import ...")
            elif isinstance(node, ast.Name) and node.id in ("PermissionEngine", "bao_mat"):
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
