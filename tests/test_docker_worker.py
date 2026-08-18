from unittest.mock import MagicMock

from visionary_tasks.workers.adapters import docker as docker_adapter


def test_run_docker_worker_forwards_environment(monkeypatch):
    client = MagicMock()
    client.containers.run.return_value = b"ok"
    monkeypatch.setattr(docker_adapter.docker, "from_env", lambda: client)

    output = docker_adapter.run_docker_worker(
        image="worker:test",
        command=["python", "task.py"],
        volumes={},
        environment={"HF_HUB_CACHE": "/cache/models/huggingface/hub"},
        use_gpu=False,
    )

    assert output == "ok"
    _, kwargs = client.containers.run.call_args
    assert kwargs["environment"] == {
        "HF_HUB_CACHE": "/cache/models/huggingface/hub"
    }
    client.close.assert_called_once_with()
