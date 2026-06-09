from pathlib import Path

from visionary_tasks.workers.adapters.langsplat import build_langsplat_live_code_volumes


def test_build_langsplat_live_code_volumes(tmp_path: Path):
    repo = tmp_path / "LangSplatV2"
    (repo / "scene").mkdir(parents=True)
    (repo / "train.py").write_text("print('train')\n", encoding="utf-8")

    volumes = build_langsplat_live_code_volumes(repo)

    assert str(repo / "train.py") in volumes
    assert volumes[str(repo / "train.py")]["bind"] == "/workspace/train.py"
    assert str(repo / "scene") in volumes
    assert volumes[str(repo / "scene")]["mode"] == "ro"
