import json
import pytest

from broadcast_controller.testing.events import HarnessEvent, HarnessEventType
from broadcast_controller.testing.results import TestResult, TestResultWriter, TestStatus


def test_result_serialization():
    result = TestResult(
        test_name="obs_connection",
        status=TestStatus.PASS,
        message="OBS connected.",
    )

    data = result.to_dict()

    assert data["test_name"] == "obs_connection"
    assert data["status"] == "pass"


def test_writer_creates_session_files(tmp_path):
    writer = TestResultWriter(tmp_path)

    writer.write_event(HarnessEvent(event_type=HarnessEventType.HARNESS_STARTED))

    writer.write_result(
        TestResult(
            test_name="obs_connection",
            status=TestStatus.PASS,
            message="Connected.",
        )
    )

    writer.close()

    assert writer.events_path.exists()
    assert writer.results_path.exists()
    assert writer.metadata_path.exists()

    event = json.loads(writer.events_path.read_text().strip())

    result = json.loads(writer.results_path.read_text().strip())

    metadata = json.loads(writer.metadata_path.read_text())

    assert event["event_type"] == "harness_started"
    assert result["status"] == "pass"
    assert metadata["status"] == "completed"


def test_writer_rejects_writes_after_close(tmp_path):
    writer = TestResultWriter(tmp_path)
    writer.close()

    with pytest.raises(RuntimeError):
        writer.write_result(
            TestResult(
                test_name="test",
                status=TestStatus.PASS,
                message="Test",
            )
        )