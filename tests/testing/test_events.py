import pytest

from broadcast_controller.testing.events import HarnessEvent, HarnessEventType


def test_event_creation():
    event = HarnessEvent(event_type=HarnessEventType.HARNESS_STARTED)

    assert event.event_type is HarnessEventType.HARNESS_STARTED
    assert event.event_id
    assert event.timestamp


def test_event_serialization():
    event = HarnessEvent(
        event_type=HarnessEventType.CAMERA_PRESET_REQUESTED,
        payload={"preset": 2},
    )

    data = event.to_dict()

    assert data["event_type"] == "camera_preset_requested"
    assert data["payload"]["preset"] == 2


def test_invalid_event_type_rejected():
    with pytest.raises(TypeError):
        HarnessEvent(event_type="invalid")