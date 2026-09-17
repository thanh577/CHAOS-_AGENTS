"""Foundation tests (T0.1).

Proves: package is importable, layout matches REPOSITORY.md,
entry point runs without side effects, test runner works.
"""

import importlib

import chaos
from chaos.main import main

SUBPACKAGES = [
    "giao_dien",
    "bo_nao",
    "tri_nho",
    "nhan_cach",
    "cong_cu",
    "bao_mat",
    "kiem_tra",
    "cau_hinh",
    "ha_tang",
]


def test_package_has_version():
    assert chaos.__version__ == "0.0.1"


def test_subpackages_importable():
    for name in SUBPACKAGES:
        module = importlib.import_module(f"chaos.{name}")
        assert module.__name__ == f"chaos.{name}"


def test_main_returns_zero(capsys):
    assert main() == 0
    out = capsys.readouterr().out
    assert "CHAOS" in out
    assert "Milestone 0" in out
