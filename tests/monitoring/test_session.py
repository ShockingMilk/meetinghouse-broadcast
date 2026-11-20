import json

from broadcast_controller.monitoring.enums import MonitoringMode
from broadcast_controller.monitoring.session import MonitoringSession


def test_session_creates_directory(tmp_path):
    session = MonitoringSession(
        mode=MonitoringMode.PASSIVE,
        output_directory=tmp_path,
    )

    assert session.session_directory.exists()
    assert session.metadata_path.exists()


def test_session_creates_metadata(tmp_path):
    session = MonitoringSession(
        mode=MonitoringMode.PASSIVE,
        output_directory=tmp_path,
    )

    metadata = json.loads(session.metadata_path.read_text(encoding="utf-8"))

    assert metadata["session_id"] == session.session_id
    assert metadata["mode"] == "passive"
    assert metadata["status"] == "running"
    assert metadata["ended_at"] is None


def test_session_close_updates_metadata(tmp_path):
    session = MonitoringSession(
        mode=MonitoringMode.PASSIVE,
        output_directory=tmp_path,
    )

    session.close()

    metadata = json.loads(session.metadata_path.read_text(encoding="utf-8"))

    assert metadata["status"] == "completed"
    assert metadata["ended_at"] is not None


def test_session_close_can_record_failure(tmp_path):
    session = MonitoringSession(
        mode=MonitoringMode.ACTIVE,
        output_directory=tmp_path,
    )

    session.close(status="failed")

    metadata = json.loads(session.metadata_path.read_text(encoding="utf-8"))

    assert metadata["status"] == "failed"


def test_session_close_is_idempotent(tmp_path):
    session = MonitoringSession(
        mode=MonitoringMode.PASSIVE,
        output_directory=tmp_path,
    )

    session.close()
    first_end_time = session.ended_at

    session.close(status="failed")

    assert session.ended_at == first_end_time
    assert session.status == "completed"