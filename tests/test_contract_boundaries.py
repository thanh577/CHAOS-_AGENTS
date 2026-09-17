"""Boundary tests: contracts stay stdlib-only and side-effect free.

Two structural guarantees no feature test can give:
1. Every import inside ``src/chaos/*/contracts/`` is stdlib or ``chaos`` itself
   (no pydantic, no SDK — dependency policy enforced by test).
2. No contract source touches network/shell/filesystem primitives.
"""

import ast
import re
import sys
from pathlib import Path

import chaos

CONTRACT_DIRS = sorted((Path(chaos.__file__).parent).glob("*/contracts"))
assert CONTRACT_DIRS, "no contracts packages found"

CONTRACT_FILES = sorted(p for d in CONTRACT_DIRS for p in d.glob("*.py"))

FORBIDDEN = [
    r"\bsocket\b",
    r"\bsubprocess\b",
    r"\burllib\b",
    r"\bhttp\.client\b",
    r"\bssl\b",
    r"\bos\.system\b",
    r"\bos\.popen\b",
    r"\bshutil\b",
    r"\bpathlib\b",
    r"\bopen\s*\(",
    r"\b__import__\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bctypes\b",
]


def _contract_sources():
    return {path: path.read_text(encoding="utf-8") for path in CONTRACT_FILES}


def test_contract_files_exist_in_expected_packages():
    owners = {path.parent.parent.name for path in CONTRACT_FILES}
    assert owners >= {"bo_nao", "cong_cu", "tri_nho", "bao_mat", "kiem_tra", "ha_tang"}


def test_imports_are_stdlib_or_chaos_only():
    stdlib = set(sys.stdlib_module_names)
    violations = []
    for path, source in _contract_sources().items():
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue  # relative import inside chaos
                roots = [node.module.split(".")[0]] if node.module else []
            else:
                continue
            for root in roots:
                if root not in stdlib and root != "chaos":
                    violations.append(f"{path.name}: {root}")
    assert violations == []


def test_no_network_shell_filesystem_primitives():
    hits = []
    for path, source in _contract_sources().items():
        for pattern in FORBIDDEN:
            if re.search(pattern, source):
                hits.append(f"{path.name}: {pattern}")
    assert hits == []
