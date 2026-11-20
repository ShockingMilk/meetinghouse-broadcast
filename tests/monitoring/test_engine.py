import json
import pytest

from broadcast_controller.monitoring.configuration import MonitoringConfiguration
from broadcast_controller.monitoring.engine import MonitoringEngine
from broadcast_controller.monitoring.enums import CollectorSafety, MonitoringMode, RecordStatus, RecordType
from broadcast_controller.monitoring.records import MonitoringRecord
from broadcast_controller.monitoring.session import MonitoringSession
from broadcast_controller.monitoring.writer import JSONLWriter


def make_configuration(tmp_path):
    return MonitoringConfiguration.from_mapping(
        {
            "monitoring": {
                "schema_version": "1.0",
                "output_directory": str(tmp_path),
                "max_file_bytes": 1024,
                "backup_count": 5,
                "default_mode": "passive",
                "modes": {
                    "passive": {
                        "allow_control_actions": True,
                        "collectors": {
                            "test": {
                                "enabled": True,
                                "interval_seconds": 5,
                            }
                        },
                    },
                    "active": {
                        "allow_control_actions": True,
                        "collectors": {
                            "test": {
                                "enabled": True,
                                "interval_seconds": 1,
                            }
                        },
                    },
                    "diagnostic": {
                        "allow_control_actions": True,
                        "collectors": {
                            "test": {
                                "enabled": True,
                                "interval_seconds": 5,
                            }
                        },
                    },
                },
            }
        },
        project_root=tmp_path,
    )


def make_record(session_id="wrong-session"):
    return MonitoringRecord(
        component="test",
        record_type=RecordType.EVENT,
        name="test_event",
        status=RecordStatus.NORMAL,
        session_id=session_id,
        mode=MonitoringMode.ACTIVE,
    )


class SuccessfulCollector:
    name = "test"
    safety = CollectorSafety.READ_ONLY

    def collect(self, context):
        return [make_record()]


class FailingCollector:
    name = "test"
    safety = CollectorSafety.READ_ONLY

    def collect(self, context):
        raise RuntimeError("Test collector failure")


class ControlCollector:
    name = "test"
    safety = CollectorSafety.CONTROL

    def collect(self, context):
        return []


def make_engine(tmp_path, mode=MonitoringMode.PASSIVE):
    configuration = make_configuration(tmp_path)

    session = MonitoringSession(
        mode=mode,
        output_directory=tmp_path,
    )

    writer = JSONLWriter(session.session_directory)

    return MonitoringEngine(
        configuration,
        session,
        writer,
    )


def read_records(session):
    records = []

    for path in session.session_directory.glob("records-*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            records.append(json.loads(line))

    return records


def test_engine_runs_collector(tmp_path):
    engine = make_engine(tmp_path)

    engine.register_collector(SuccessfulCollector())

    count = engine.run_once()

    assert count == 1


def test_engine_uses_session_identity(tmp_path):
    engine = make_engine(tmp_path)

    engine.register_collector(SuccessfulCollector())

    engine.run_once()

    records = read_records(engine.session)

    assert records[0]["session_id"] == engine.session.session_id

    assert records[0]["mode"] == "passive"


def test_engine_skips_disabled_collector(tmp_path):
    engine = make_engine(tmp_path)

    engine.configuration.modes["passive"]["collectors"]["test"]["enabled"] = False

    engine.register_collector(SuccessfulCollector())

    assert engine.run_once() == 0


def test_engine_records_collector_failure(tmp_path):
    engine = make_engine(tmp_path)

    engine.register_collector(FailingCollector())

    count = engine.run_once()

    records = read_records(engine.session)

    assert count == 1
    assert records[0]["status"] == "failure"
    assert records[0]["record_type"] == "diagnostic"
    assert records[0]["attributes"]["error_type"] == "RuntimeError"


def test_passive_mode_rejects_control_collector(tmp_path):
    engine = make_engine(tmp_path, MonitoringMode.PASSIVE)

    with pytest.raises(PermissionError):
        engine.register_collector(ControlCollector())


def test_diagnostic_mode_rejects_control_collector(tmp_path):
    engine = make_engine(tmp_path, MonitoringMode.DIAGNOSTIC)

    with pytest.raises(PermissionError):
        engine.register_collector(ControlCollector())


def test_active_mode_can_register_control_collector(tmp_path):
    engine = make_engine(tmp_path, MonitoringMode.ACTIVE)

    engine.register_collector(ControlCollector())


def test_engine_rejects_duplicate_collector(tmp_path):
    engine = make_engine(tmp_path)

    engine.register_collector(SuccessfulCollector())

    with pytest.raises(ValueError):
        engine.register_collector(SuccessfulCollector())


def test_engine_cannot_run_after_close(tmp_path):
    engine = make_engine(tmp_path)

    engine.close()

    with pytest.raises(RuntimeError):
        engine.run_once()


def test_engine_close_updates_session(tmp_path):
    engine = make_engine(tmp_path)

    engine.close()

    assert engine.session.status == "completed"
    assert engine.session.ended_at is not None