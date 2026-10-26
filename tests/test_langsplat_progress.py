"""The shared package can run in a worker without the backend or GPU packages."""
import os
from pathlib import Path
import subprocess
import sys

from visionary_progress import ProgressReporter, read_progress_events


def test_worker_installs_and_imports_only_the_shared_progress_package(tmp_path):
    import shutil

    repository = Path(__file__).resolve().parents[1]
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy2(repository / "pyproject.toml", source)
    shutil.copytree(repository / "visionary_progress", source / "visionary_progress", ignore=shutil.ignore_patterns("__pycache__"))
    install = tmp_path / "installed"
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--quiet", "--no-deps", "--no-build-isolation",
        "--no-index", "--target", str(install), str(source),
    ], check=True, capture_output=True, text=True)
    assert not (install / "visionary_tasks").exists()
    event_file = tmp_path / "events" / "langsplat.jsonl"
    for level in (3, 1):
        context = ProgressReporter(event_file, "langsplat", {"name": "train", "level": level}, f"训练 level={level}")
        environment = {**os.environ, **context.environment(), "PYTHONPATH": str(install)}
        subprocess.run([sys.executable, "-S", "-c", '''
import sys
from visionary_progress import ProgressReporter
progress = ProgressReporter.from_env()
progress.record(event_type="step_started", message="加载训练数据")
progress.record(completed=250, total=1000, unit="iteration", message="训练中")
progress.record(completed=1000, total=1000, unit="iteration", event_type="step_completed")
assert "torch" not in sys.modules and "visionary_tasks" not in sys.modules
'''], cwd=tmp_path, env=environment, check=True)
    events = read_progress_events(event_file)
    assert [event.current_step.id["level"] for event in events] == [3, 3, 3, 1, 1, 1]
    assert events[0].current_step.completed is None
    assert events[1].progress is None
    assert events[1].current_step.progress == 0.25
    assert events[1].iteration == 250
    assert events[2].current_step.progress == 1.0
    assert events[3].current_step.completed is None


def test_training_progress_is_optional_for_standalone_runs(monkeypatch):
    monkeypatch.delenv("VISIONARY_PROGRESS_FILE", raising=False)
    ProgressReporter.from_env().record(completed=1, total=1000, unit="iteration")
