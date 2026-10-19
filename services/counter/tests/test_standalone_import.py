"""Integration and subprocess execution tests for standalone and dual-mode counter service."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
COUNTER_DIR = REPO_ROOT / "services" / "counter"


def _get_sanitized_env() -> dict[str, str]:
    """Returns environment variables with PYTHONPATH removed."""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return env


def _setup_isolated_counter_dir(target_dir: Path) -> Path:
    """Copies counter service files into an isolated directory structure mimicking standalone container."""
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(COUNTER_DIR / "main.py", target_dir / "main.py")
    shutil.copy(COUNTER_DIR / "benchmark.py", target_dir / "benchmark.py")
    shutil.copytree(COUNTER_DIR / "src", target_dir / "src")
    return target_dir


def test_standalone_isolated_main_help(tmp_path):
    """Verify python main.py --help executes successfully in a standalone directory without repo root."""
    isolated_dir = _setup_isolated_counter_dir(tmp_path / "standalone_app")
    env = _get_sanitized_env()

    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        cwd=str(isolated_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, f"main.py --help failed: {result.stderr}"
    assert "Edge Poultry Counter Service" in result.stdout
    assert "--line-id" in result.stdout


def test_standalone_isolated_benchmark_help(tmp_path):
    """Verify python benchmark.py --help executes successfully in a standalone directory without repo root."""
    isolated_dir = _setup_isolated_counter_dir(tmp_path / "standalone_app")
    env = _get_sanitized_env()

    result = subprocess.run(
        [sys.executable, "benchmark.py", "--help"],
        cwd=str(isolated_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, f"benchmark.py --help failed: {result.stderr}"
    assert "Pipeline Benchmark Harness" in result.stdout
    assert "--frames" in result.stdout


def test_standalone_isolated_import(tmp_path):
    """Verify main and benchmark can be imported in an isolated standalone directory."""
    isolated_dir = _setup_isolated_counter_dir(tmp_path / "standalone_app")
    env = _get_sanitized_env()

    cmd = (
        "import main, benchmark; "
        "assert hasattr(main, 'CounterService'); "
        "assert hasattr(benchmark, 'run_benchmark'); "
        "print('STANDALONE_IMPORT_SUCCESS')"
    )

    result = subprocess.run(
        [sys.executable, "-c", cmd],
        cwd=str(isolated_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, f"Import failed: {result.stderr}"
    assert "STANDALONE_IMPORT_SUCCESS" in result.stdout


def test_standalone_subprocess_main_help_from_counter_dir():
    """Verify running python main.py --help directly from services/counter directory without PYTHONPATH."""
    env = _get_sanitized_env()

    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        cwd=str(COUNTER_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, f"main.py --help failed: {result.stderr}"
    assert "Edge Poultry Counter Service" in result.stdout
    assert "--line-id" in result.stdout


def test_standalone_subprocess_benchmark_help_from_counter_dir():
    """Verify running python benchmark.py --help directly from services/counter directory without PYTHONPATH."""
    env = _get_sanitized_env()

    result = subprocess.run(
        [sys.executable, "benchmark.py", "--help"],
        cwd=str(COUNTER_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, f"benchmark.py --help failed: {result.stderr}"
    assert "Pipeline Benchmark Harness" in result.stdout
    assert "--frames" in result.stdout


def test_monorepo_module_main_help():
    """Verify running python -m services.counter.main --help from monorepo root."""
    env = _get_sanitized_env()

    result = subprocess.run(
        [sys.executable, "-m", "services.counter.main", "--help"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, f"python -m services.counter.main --help failed: {result.stderr}"
    assert "Edge Poultry Counter Service" in result.stdout


def test_monorepo_module_benchmark_help():
    """Verify running python -m services.counter.benchmark --help from monorepo root."""
    env = _get_sanitized_env()

    result = subprocess.run(
        [sys.executable, "-m", "services.counter.benchmark", "--help"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, f"python -m services.counter.benchmark --help failed: {result.stderr}"
    assert "Pipeline Benchmark Harness" in result.stdout


def test_standalone_import_when_counter_dir_is_cwd(monkeypatch):
    """Verify importing main when services/counter is the current working directory."""
    monkeypatch.chdir(COUNTER_DIR)
    if str(COUNTER_DIR) not in sys.path:
        monkeypatch.syspath_prepend(str(COUNTER_DIR))

    import main
    import benchmark

    assert hasattr(main, "CounterService")
    assert hasattr(main, "parse_args")
    assert hasattr(benchmark, "run_benchmark")
