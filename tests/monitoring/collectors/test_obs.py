from types import SimpleNamespace

import pytest

from broadcast_controller.monitoring.collectors.obs import OBSCollector
from broadcast_controller.monitoring.engine import CollectorContext
from broadcast_controller.monitoring.enums import CollectorSafety, MonitoringMode, RecordStatus


def make_context():
    return CollectorContext(
        session_id="test-session",
        mode=MonitoringMode.PASSIVE,
        settings={},
    )


class FakeOBSClient:
    def __init__(self, responses=None, errors=None):
        self.responses = responses or {}
        self.errors = errors or {}
        self.requests = []
        self.disconnected = False

    def get_version(self):
        if "GetVersion" in self.errors:
            raise self.errors["GetVersion"]

        return SimpleNamespace(
            obs_version="33.0.0",
            obs_web_socket_version="5.5.0",
            platform="linux",
            platform_description="Ubuntu",
        )

    def send(self, request_type, request_data=None, raw=False):
        self.requests.append((request_type, request_data, raw))

        if request_type in self.errors:
            raise self.errors[request_type]

        return self.responses.get(request_type, {})

    def disconnect(self):
        self.disconnected = True


@pytest.fixture
def config():
    return {
        "obs": {
            "obs": {
                "websocket": {
                    "host": "127.0.0.1",
                    "port": 4455,
                    "password": "test-password",
                    "timeout": 5,
                }
            }
        },
        "camera": {
            "camera": {
                "monitoring": {
                    "obs_input_name": "Meetinghouse Camera",
                }
            }
        },
    }


def make_responses():
    return {
        "GetCurrentProgramScene": {
            "currentProgramSceneName": "01 - Speaker",
        },
        "GetVirtualCamStatus": {
            "outputActive": True,
        },
        "GetStats": {
            "cpuUsage": 12.5,
            "memoryUsage": 1024.0,
            "activeFps": 30.0,
            "renderTotalFrames": 1000,
            "renderMissedFrames": 2,
            "outputTotalFrames": 1000,
            "outputSkippedFrames": 1,
            "unrecognizedField": "must not be recorded",
        },
        "GetInputList": {
            "inputs": [
                {
                    "inputName": "Meetinghouse Camera",
                    "inputKind": "ffmpeg_source",
                },
                {
                    "inputName": "Microphone",
                    "inputKind": "wasapi_input_capture",
                },
            ]
        },
        "GetSourceActive": {
            "videoActive": True,
            "videoShowing": True,
        },
    }


def test_obs_collector_is_read_only(config):
    collector = OBSCollector(config)

    assert collector.safety is CollectorSafety.READ_ONLY


def test_collects_obs_status_and_camera_input(config):
    client = FakeOBSClient(responses=make_responses())

    collector = OBSCollector(
        config,
        client_factory=lambda **kwargs: client,
    )

    records = collector.collect(make_context())
    by_name = {
        (record.component, record.name): record
        for record in records
    }

    assert by_name[("obs", "websocket_connection")].status is RecordStatus.NORMAL
    assert by_name[("obs", "version")].value["obs_version"] == "33.0.0"
    assert by_name[("obs", "current_program_scene")].value == "01 - Speaker"

    virtual_camera = by_name[("obs", "virtual_camera")]
    assert virtual_camera.value["active"] is True

    camera_activity = by_name[("camera", "obs_input_activity")]
    assert camera_activity.status is RecordStatus.NORMAL
    assert camera_activity.value == {
        "video_active": True,
        "video_showing": True,
    }

    assert client.disconnected is True


def test_stats_only_record_whitelisted_fields(config):
    client = FakeOBSClient(responses=make_responses())

    collector = OBSCollector(
        config,
        client_factory=lambda **kwargs: client,
    )

    records = collector.collect(make_context())
    stats = next(record for record in records if record.name == "performance")

    assert stats.status is RecordStatus.NORMAL
    assert "cpuUsage" in stats.value
    assert "unrecognizedField" not in stats.value


def test_obs_connection_failure_returns_unavailable(config):
    def fail_connection(**kwargs):
        raise ConnectionError("OBS unavailable")

    collector = OBSCollector(
        config,
        client_factory=fail_connection,
    )

    records = collector.collect(make_context())

    assert len(records) == 1
    assert records[0].name == "websocket_connection"
    assert records[0].status is RecordStatus.UNAVAILABLE


def test_individual_request_failure_does_not_stop_other_metrics(config):
    responses = make_responses()
    client = FakeOBSClient(
        responses=responses,
        errors={
            "GetStats": RuntimeError("Stats unavailable"),
        },
    )

    collector = OBSCollector(
        config,
        client_factory=lambda **kwargs: client,
    )

    records = collector.collect(make_context())
    by_name = {record.name: record for record in records}

    assert by_name["performance"].status is RecordStatus.UNAVAILABLE
    assert by_name["current_program_scene"].status is RecordStatus.NORMAL
    assert by_name["virtual_camera"].status is RecordStatus.NORMAL


def test_missing_camera_input_name_is_unavailable(config):
    config["camera"]["camera"]["monitoring"]["obs_input_name"] = ""

    client = FakeOBSClient(responses=make_responses())

    collector = OBSCollector(
        config,
        client_factory=lambda **kwargs: client,
    )

    records = collector.collect(make_context())

    camera_record = next(
        record for record in records
        if record.component == "camera"
    )

    assert camera_record.status is RecordStatus.UNAVAILABLE
    assert camera_record.message == "No OBS camera input name is configured."


def test_missing_camera_input_is_unavailable(config):
    responses = make_responses()
    responses["GetInputList"] = {
        "inputs": [
            {
                "inputName": "Other Source",
                "inputKind": "ffmpeg_source",
            }
        ]
    }

    client = FakeOBSClient(responses=responses)

    collector = OBSCollector(
        config,
        client_factory=lambda **kwargs: client,
    )

    records = collector.collect(make_context())

    camera_record = next(
        record for record in records
        if record.component == "camera"
    )

    assert camera_record.status is RecordStatus.UNAVAILABLE
    assert "not found" in camera_record.message


def test_obs_collector_uses_only_read_requests(config):
    client = FakeOBSClient(responses=make_responses())

    collector = OBSCollector(
        config,
        client_factory=lambda **kwargs: client,
    )

    collector.collect(make_context())

    requested = {request[0] for request in client.requests}

    assert requested.issubset(
        {
            "GetCurrentProgramScene",
            "GetVirtualCamStatus",
            "GetStats",
            "GetInputList",
            "GetSourceActive",
        }
    )

    assert not requested.intersection(
        {
            "SetCurrentProgramScene",
            "StartVirtualCam",
            "StopVirtualCam",
            "SetInputSettings",
        }
    )