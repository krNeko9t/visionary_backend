import importlib.util
from pathlib import Path

import numpy as np
import pytest

_SCALES_PATH = (
    Path(__file__).resolve().parents[1]
    / "docker_workers"
    / "3dgsToPc"
    / "gs_to_pc"
    / "scales.py"
)


def _ensure_3d_scales():
    spec = importlib.util.spec_from_file_location("gs_to_pc_scales", _SCALES_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.ensure_3d_scales


def test_ensure_3d_scales_keeps_3dgs():
    ensure_3d_scales = _ensure_3d_scales()
    scales = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
    np.testing.assert_array_equal(ensure_3d_scales(scales), scales)


def test_ensure_3d_scales_pads_2dgs_thin_axis():
    ensure_3d_scales = _ensure_3d_scales()
    scales = np.array([[0.5, 1.0], [-1.0, 0.0]])
    padded = ensure_3d_scales(scales)
    assert padded.shape == (2, 3)
    np.testing.assert_array_equal(padded[:, :2], scales)
    np.testing.assert_allclose(padded[:, 2], scales.min(axis=1) - 4.0)


def test_ensure_3d_scales_rejects_other_dims():
    ensure_3d_scales = _ensure_3d_scales()
    with pytest.raises(ValueError, match="必须是 2"):
        ensure_3d_scales(np.array([[0.1]]))
