from docker_workers.LangSplatV2.utils.image_scale import AUTO_MAX_SIDE, scaled_resolution


def test_auto_resolution_caps_long_side_to_1024():
    width, height = scaled_resolution(5712, 4284, -1)
    assert AUTO_MAX_SIDE == 1024
    assert width == 1024
    assert height == 768


def test_auto_resolution_keeps_images_already_within_1k():
    assert scaled_resolution(800, 600, -1) == (800, 600)


def test_explicit_target_width_still_scales_by_width():
    assert scaled_resolution(5712, 4284, 256) == (256, 192)


def test_integer_downsample_factors():
    assert scaled_resolution(1600, 1200, 2) == (800, 600)
