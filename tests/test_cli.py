"""Tests for the `python -m qsim` onboarding entry point (qsim/__main__.py)."""
from qsim.__main__ import main


def test_check_runs_and_all_domains_feasible(capsys):
    rc = main(["check"])
    out = capsys.readouterr().out
    assert rc == 0                                   # every shipped default is feasible
    for label in ("QKD link", "magnetometer", "Qubit processor", "Quantum RNG"):
        assert label in out
    assert "feasible" in out and "INFEASIBLE" not in out


def test_no_args_defaults_to_check(capsys):
    assert main([]) == 0
    assert "virtual quantum bench" in capsys.readouterr().out


def test_help_and_unknown_command():
    assert main(["--help"]) == 0
    assert main(["wat"]) == 2
