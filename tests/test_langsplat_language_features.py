from pathlib import Path

import numpy as np
import pytest

from visionary_tasks.config.loader import _resolve_stage_config
from visionary_tasks.settings.langsplat import LangSplatJobConfig


def test_decode_dense_language_feature_gathers_on_requested_device(tmp_path: Path):
    pytest.importorskip("torch")
    from docker_workers.LangSplatV2.utils.language_features import (
        decode_dense_language_feature,
        load_compact_language_maps,
    )

    height, width, channels = 3, 4, 8
    seg_map = np.array(
        [
            [[0, 1, 0, 1], [1, 0, -1, 1], [0, 0, 1, 1]],
        ],
        dtype=np.int32,
    )
    feature_map = np.array(
        [
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    np.save(tmp_path / "frame_s.npy", seg_map)
    np.save(tmp_path / "frame_f.npy", feature_map)

    loaded_seg, loaded_feat = load_compact_language_maps(str(tmp_path), "frame")
    dense, mask = decode_dense_language_feature(loaded_seg, loaded_feat, 0, device="cpu")

    assert dense.shape == (channels, height, width)
    assert mask.tolist() == [[[True, True, True, True], [True, True, False, True], [True, True, True, True]]]
    assert dense[:, 0, 0].tolist() == feature_map[0].tolist()
    assert dense[:, 0, 1].tolist() == feature_map[1].tolist()


def test_default_and_high_presets_keep_1k_and_cpu_images():
    default_config = LangSplatJobConfig.from_merged_dict(_resolve_stage_config("langsplat"))
    high_config = LangSplatJobConfig.from_merged_dict(_resolve_stage_config("langsplat", preset="high"))

    assert default_config.model.resolution == -1
    assert default_config.preprocess.resolution == -1
    assert default_config.model.data_device == "cpu"
    assert high_config.model.resolution == -1
    assert high_config.model.data_device == "cpu"
