from visionary_tasks.config.registry import stage_preset_paths


def test_colmap_presets_are_discovered_from_config_dir():
    presets = stage_preset_paths("colmap")
    assert set(presets) == {"general", "video", "fast", "fisheye"}


def test_stage_without_extra_yaml_has_no_presets():
    assert stage_preset_paths("3dgs-to-pc") == {}
