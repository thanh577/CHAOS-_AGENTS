"""Brain-boundary tests (T1.5): M1 modules stay dependency- and scope-clean.

- imports are stdlib / chaos / sqlalchemy-free (no SDK, no ORM in the brain path);
- no permission-engine or tool-executor references anywhere in bo_nao;
- no secret-shaped literals in source under test.
"""

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

import chaos.bo_nao.brain
import chaos.bo_nao.http_transport
import chaos.bo_nao.openai_compat

MODULE_FILES = [
    Path(chaos.bo_nao.brain.__file__),
    Path(chaos.bo_nao.http_transport.__file__),
    Path(chaos.bo_nao.openai_compat.__file__),
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
    r"\bPermissionEngine\b",
    r"\bbao_mat\b",
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
