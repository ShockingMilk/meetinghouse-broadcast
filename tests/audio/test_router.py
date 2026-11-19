import pytest

from broadcast_controller.audio.router import AudioRouter

@pytest.fixture
def config():
    return {
        "audio": {
            "audio": {
                "enabled": True,
                "virtual_device": {
                    "sink_name": "meetinghouse_broadcast",
                    "description": "Meetinghouse_Broadcast",
                    "sample_rate": 48000,
                    "channels": 2,
                    "microphone_source_name": "meetinghouse_broadcast_mic",
                    "microphone_description": "Meetinghouse Broadcast Microphone",
                },
                "microphone": {
                    "preferred_source": "",
                    "fallback_source": "internal_mic",
                    "latency_msec": 50,
                },
                "behavior": {
                    "cleanup_virtual_device_on_shutdown": True,
                },
            }
        }
    }

def test_monitor_name(config):
    router = AudioRouter(config)

    assert router.monitor_name == (
        "meetinghouse_broadcast.monitor"
    )

def test_virtual_microphone_name(config):
    router = AudioRouter(config)

    assert router.microphone_input_name == "meetinghouse_broadcast_mic"

def test_default_microphone_selected(config, monkeypatch):
    router = AudioRouter(config)

    monkeypatch.setattr(
        router,
        "_get_default_source",
        lambda: "internal_mic",
    )

    monkeypatch.setattr(
        router,
        "_source_exists",
        lambda source: source == "internal_mic",
    )

    assert router.get_microphone_source() == "internal_mic"

def test_preferred_microphone_selected(config, monkeypatch):
    config["audio"]["audio"]["microphone"]["preferred_source"] = "usb_mic"

    router = AudioRouter(config)

    monkeypatch.setattr(
        router,
        "_source_exists",
        lambda source: source in {"usb_mic", "internal_mic"},
    )

    monkeypatch.setattr(
        router,
        "_get_default_source",
        lambda: "internal_mic",
    )

    assert router.get_microphone_source() == "usb_mic"

def test_no_microphone_raises_error(config, monkeypatch):
    router = AudioRouter(config)

    monkeypatch.setattr(
        router,
        "_get_default_source",
        lambda: "unavailable",
    )

    monkeypatch.setattr(
        router,
        "_source_exists",
        lambda source: False,
    )

    with pytest.raises(RuntimeError):
        router.get_microphone_source()
