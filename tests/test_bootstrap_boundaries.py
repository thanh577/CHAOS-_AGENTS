"""Security-boundary tests for config + bootstrap + entrypoint.

Static guarantees for the M0 runtime skeleton:
1. No imports outside stdlib / ``chaos`` (no SDK, no dotenv, no typer…).
2. No network / shell / filesystem primitives in these modules.
3. ``.env`` files are never referenced — process environment only.
4. No secret-shaped literals in source under test.
"""

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

import chaos
import chaos.cau_hinh
import chaos.ha_tang.application
import chaos.ha_tang.logging
import chaos.ha_tang.runtime
import chaos.main

MODULES = (
    chaos.cau_hinh,
    chaos.main,
    chaos.ha_tang.application,
    chaos.ha_tang.logging,
    chaos.ha_tang.runtime,
)

MODULE_FILES = [Path(m.__file__) for m in MODULES] + [
    Path(chaos.cau_hinh.__file__).parent / "settings.py",
    Path(chaos.cau_hinh.__file__).parent / "secrets.py",
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
    r"\.env\b",
    r"\bdotenv\b",
]

# T0.7 exception: application.py assembles the configured database path with
# pathlib and prepares the storage directory (mkdir). Both stay inside the
# operator-configured storage location — reviewed, in-scope. Every other
# module keeps the full ban.
EXEMPT = {"application.py": {r"\bpathlib\b"}}


def _code_only(path: Path) -> str:
    """Source minus strings/comments, so prose can't trip the scan."""
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


def test_no_network_shell_filesystem_or_dotenv():
    hits = []
    for path in MODULE_FILES:
        code = _code_only(path)
        allowed = EXEMPT.get(path.name, set())
        for pattern in FORBIDDEN:
            if pattern in allowed:
                continue
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
