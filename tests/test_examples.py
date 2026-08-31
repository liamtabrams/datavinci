"""Smoke tests: run the example scripts end-to-end, offline, so they can't
silently break as the library evolves. Executed as subprocesses with a headless
matplotlib backend and a temp working directory for any output files.
"""

import subprocess
import sys
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _run(script: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(EXAMPLES / script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={"MPLBACKEND": "Agg", "PATH": __import__("os").environ.get("PATH", "")},
    )


def test_backtest_demo_runs(tmp_path):
    proc = _run("backtest_demo.py", [], tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "Backtest:" in proc.stdout


def test_compare_strategies_runs_and_lists_all(tmp_path):
    proc = _run("compare_strategies.py", ["--outdir", str(tmp_path / "out")], tmp_path)
    assert proc.returncode == 0, proc.stderr
    # Every strategy (and the baseline) should appear in the printed table.
    for name in (
        "SMA crossover",
        "RSI mean-reversion",
        "Bollinger breakout",
        "MACD crossover",
        "Buy & hold",
    ):
        assert name in proc.stdout
    # The comparison chart should have been written.
    assert (tmp_path / "out" / "equity_comparison.png").exists()
