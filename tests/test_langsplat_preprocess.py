from visionary_tasks.settings.langsplat import LangSplatJobConfig


def test_preprocess_command_injects_container_sam_path():
    config = LangSplatJobConfig.from_merged_dict({"preprocess": {"resolution": 256}})
    command = config.to_preprocess_command(
        "/job/colmap",
        sam_ckpt_path="/workspace/ckpts/sam_vit_h_4b8939.pth",
    )
    assert command[command.index("--dataset_path") + 1] == "/job/colmap"
    assert command[command.index("--resolution") + 1] == "256"
    assert command[command.index("--sam_ckpt_path") + 1] == "/workspace/ckpts/sam_vit_h_4b8939.pth"
