from __future__ import annotations

from typing import Any

MESH_ROUTES = frozenset({"mesh_first", "3dgs_first"})
DEFAULT_MESH_ROUTE = "mesh_first"


def get_mesh_route(options: dict[str, Any]) -> str:
    route = str(options.get("mesh_route", DEFAULT_MESH_ROUTE))
    if route not in MESH_ROUTES:
        raise ValueError(
            f"未知 mesh_route: {route}，可选值: {', '.join(sorted(MESH_ROUTES))}"
        )
    return route


def mesh_required_stages(route: str) -> tuple[str, ...]:
    if route == "3dgs_first":
        return ("colmap", "3dgs", "gaussian-wrapping")
    return ("colmap", "gw-train", "gaussian-wrapping")
