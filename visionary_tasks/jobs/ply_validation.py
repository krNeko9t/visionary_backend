from __future__ import annotations

import re

REQUIRED_PLY_PROPERTIES = {"x", "y", "z", "opacity", "f_dc_0", "f_dc_1", "f_dc_2"}
PLY_PROPERTY_PATTERN = re.compile(r"^property\s+\S+\s+(\S+)", re.MULTILINE)


def validate_native_3dgs_ply(content: bytes) -> None:
    if not content.startswith(b"ply"):
        raise ValueError("PLY 文件格式无效")

    header_end = content.find(b"end_header")
    if header_end < 0:
        raise ValueError("PLY 文件缺少 end_header")

    header = content[:header_end].decode("utf-8", errors="replace")
    properties = set(PLY_PROPERTY_PATTERN.findall(header))
    missing = sorted(REQUIRED_PLY_PROPERTIES - properties)
    if missing:
        raise ValueError(f"PLY 缺少必要字段: {', '.join(missing)}")
    if not any(name.startswith("f_rest_") for name in properties):
        raise ValueError("PLY 缺少 f_rest_* 字段")
    if not any(name.startswith("scale_") for name in properties):
        raise ValueError("PLY 缺少 scale_* 字段")
    if not any(name.startswith("rot_") for name in properties):
        raise ValueError("PLY 缺少 rot_* 字段")
