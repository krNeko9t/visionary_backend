from visionary_tasks.config.loader import _resolve_stage_config
from visionary_tasks.settings.colmap import ColmapJobConfig


def _load_colmap(preset: str | None = None) -> ColmapJobConfig:
    return ColmapJobConfig.from_merged_dict(_resolve_stage_config("colmap", preset=preset))


def test_general_preset_defaults():
    config = _load_colmap("general")
    converter = config.converter
    assert converter.camera == "OPENCV"
    assert converter.matcher == "exhaustive"
    assert converter.sift.max_num_features == 16384
    assert converter.mapper.ba_global_function_tolerance == 0.000001


def test_video_preset_uses_sequential_matcher():
    config = _load_colmap("video")
    assert config.converter.matcher == "sequential"
    assert config.converter.mapper.multiple_models == 0


def test_fast_preset_limits_resolution():
    config = _load_colmap("fast")
    assert config.converter.sift.max_image_size == 2048
    assert config.converter.sift.max_num_features == 8192


def test_fisheye_preset_camera_model():
    config = _load_colmap("fisheye")
    assert config.converter.camera == "OPENCV_FISHEYE"


def test_override_wins_over_preset():
    merged = _resolve_stage_config(
        "colmap",
        preset="fast",
        override={"converter": {"matcher": "sequential", "sift": {"max_num_features": 4096}}},
    )
    config = ColmapJobConfig.from_merged_dict(merged)
    assert config.converter.matcher == "sequential"
    assert config.converter.sift.max_num_features == 4096
    assert config.converter.sift.max_image_size == 2048


def test_to_convert_command_includes_resolved_flags():
    config = _load_colmap("video")
    command = config.to_convert_command("/job")
    assert command[command.index("--source_path") + 1] == "/job"
    assert command[command.index("--matcher") + 1] == "sequential"
    assert command[command.index("--sift_max_num_features") + 1] == "16384"
    assert command[command.index("--mapper_multiple_models") + 1] == "0"
