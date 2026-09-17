"""Observability-boundary tests: T0.4 adds stdlib-only, side-effect-free code.

Extends the T0.2/T0.3 boundary scans to the new modules: no network,
subprocess, shell, provider SDK, database or UI runtimes; imports stay
stdlib-or-chaos; no secret-shaped literals in source.
"""

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

import chaos.ha_tang.context
import chaos.ha_tang.contracts.errors
import chaos.ha_tang.contracts.events
import chaos.ha_tang.logging
import chaos.ha_tang.redaction

MODULE_FILES = [
    Path(module.__file__)
    for module in (
        chaos.ha_tang.contracts.errors,
        chaos.ha_tang.contracts.events,
        chaos.ha_tang.redaction,
        chaos.ha_tang.context,
        chaos.ha_tang.logging,
    )
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
    r"\bpathlib\b",
    r"\bopen\s*\(",
    r"\b__import__\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bctypes\b",
    r"\bsqlite3\b",
    r"\bsqlalchemy\b",
    r"\bopentelemetry\b",
    r"\bstructlog\b",
    r"\bloguru\b",
    r"\bpydantic\b",
    r"\bdotenv\b",
    r"\bplaywright\b",
    r"\bPySide6\b",
    r"\bopenai\b",
    r"\banthropic\b",
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
