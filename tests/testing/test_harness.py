import pytest

from pathlib import Path
from types import SimpleNamespace

from broadcast_controller.testing.harness import ActiveTestHarness


def test_harness_refuses_running_controller(tmp_path, monkeypatch):
    pid_file = tmp_path / "controller.pid"
    pid_file.write_text("12345")

    harness = ActiveTestHarness(
        config={},
        state_directory=tmp_path,
    )

    monkeypatch.setattr(
        "broadcast_controller.testing.harness.is_process_running",
        lambda pid: True,
    )

    with pytest.raises(RuntimeError, match="Broadcast controller is running"):
        harness.check_controller_stopped()


def test_harness_allows_stopped_controller(tmp_path, monkeypatch):
    harness = ActiveTestHarness(
        config={},
        state_directory=tmp_path,
    )

    monkeypatch.setattr(
        "broadcast_controller.testing.harness.is_process_running",
        lambda pid: False,
    )

    harness.check_controller_stopped()


def test_harness_requires_exact_confirmation(tmp_path):
    harness = ActiveTestHarness(
        config={},
        state_directory=tmp_path,
        input_fn=lambda prompt: "yes",
        output_fn=lambda message: None,
    )

    with pytest.raises(RuntimeError, match="confirmation"):
        harness.confirm_test_environment()

def test_camera_input_activity_uses_get_source_active(tmp_path):
    class FakeClient:
        def __init__(self):
            self.request = None

        def send(self, request_type, request_data=None, raw=False):
            self.request = (request_type, request_data, raw)

            return {
                "videoActive": True,
                "videoShowing": True,
            }

    client = FakeClient()

    config = {
        "camera": {
            "camera": {
                "monitoring": {
                    "obs_input_name": "Meetinghouse Camera",
                }
            }
        }
    }

    harness = ActiveTestHarness(
        config=config,
        state_directory=tmp_path,
    )

    harness.obs = SimpleNamespace(client=client)

    activity = harness._get_camera_input_activity()

    assert client.request == (
        "GetSourceActive",
        {"sourceName": "Meetinghouse Camera"},
        True,
    )

    assert activity == {
        "video_active": True,
        "video_showing": True,
        "input_name": "Meetinghouse Camera",
    }