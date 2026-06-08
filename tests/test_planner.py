import pytest

from visionary_tasks.domain.jobs import JobSpec
from visionary_tasks.services.planner import plan_pipeline


def test_plan_point_cloud_outputs():
    plan = plan_pipeline(JobSpec(outputs=["point_cloud"]))
    assert plan.stages == ("colmap", "3dgs")


def test_plan_mesh_outputs():
    plan = plan_pipeline(JobSpec(outputs=["mesh"]))
    assert plan.stages == ("colmap", "3dgs", "gaussian-wrapping")


def test_plan_mesh_from_native_ply():
    plan = plan_pipeline(
        JobSpec(
            outputs=["mesh"],
            options={"input_mode": "native_3dgs_ply", "iteration": 30000},
        )
    )
    assert plan.stages == ("3dgs-to-pc",)


def test_native_ply_rejects_point_cloud_output():
    with pytest.raises(ValueError, match="不支持输出类型"):
        plan_pipeline(
            JobSpec(
                outputs=["point_cloud"],
                options={"input_mode": "native_3dgs_ply"},
            )
        )


def test_plan_language_features_option_adds_language_model():
    plan = plan_pipeline(
        JobSpec(outputs=["point_cloud"], options={"language_features": True})
    )
    assert "language_model" in plan.outputs
    assert plan.stages == ("colmap", "3dgs", "langsplat")


def test_advanced_stage_override():
    plan = plan_pipeline(
        JobSpec(
            outputs=["point_cloud"],
            advanced={"stages": ["colmap", "3dgs"]},
        )
    )
    assert plan.stages == ("colmap", "3dgs")


def test_advanced_stage_override_requires_dependencies():
    with pytest.raises(ValueError, match="依赖"):
        plan_pipeline(
            JobSpec(
                outputs=["point_cloud"],
                advanced={"stages": ["3dgs"]},
            )
        )


def test_unknown_output_rejected():
    with pytest.raises(ValueError, match="未知输出类型"):
        plan_pipeline(JobSpec(outputs=["unknown"]))
