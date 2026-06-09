from visionary_tasks.settings.langsplat import LangSplatJobConfig


def test_langsplat_export_command_uses_job_paths():
    config = LangSplatJobConfig.from_merged_dict({})
    command = config.to_export_command(
        model_root="/job/langsplatv2",
        output_dir="/job/langsplat_export",
        checkpoint=10000,
    )
    assert command[0:2] == ["python", "export_lsv2_final_product.py"]
    assert command[command.index("--model_root") + 1] == "/job/langsplatv2"
    assert command[command.index("--output_dir") + 1] == "/job/langsplat_export"
    assert "--checkpoint" in command
    assert command[command.index("--checkpoint") + 1] == "10000"
    assert "--levels" in command
    assert command[command.index("--levels") + 1 : command.index("--levels") + 4] == ["1", "2", "3"]
    assert "--queries" in command
    assert "elephant" in command


def test_langsplat_training_feature_levels_fallback():
    config = LangSplatJobConfig.from_merged_dict({"model": {"feature_levels": [], "feature_level": 2}})
    assert config.training_feature_levels() == [2]


def test_langsplat_export_checkpoint_prefers_explicit_value():
    config = LangSplatJobConfig.from_merged_dict(
        {
            "export": {"checkpoint": 6000},
            "training": {"checkpoint_iterations": [2000, 10000]},
        }
    )
    assert config.export_checkpoint() == 6000
