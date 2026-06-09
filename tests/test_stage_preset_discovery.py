from visionary_tasks.config.registry import stage_preset_paths


def test_colmap_presets_are_discovered_from_config_dir():
    presets = stage_preset_paths("colmap")
    assert set(presets) == {"general", "video", "fast", "fisheye"}


def test_langsplat_presets_are_discovered_from_config_dir():
    presets = stage_preset_paths("langsplat")
    assert set(presets) == {"small", "high", "full"}
