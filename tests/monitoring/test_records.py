import json
import pytest

from broadcast_controller.monitoring.enums import MonitoringMode, RecordStatus, RecordType
from broadcast_controller.monitoring.records import MonitoringRecord


def make_record():
    return MonitoringRecord(
        component="network",
        record_type=RecordType.MEASUREMENT,
        name="wifi_signal",
        value=-58,
        unit="dBm",
        status=RecordStatus.NORMAL,
        session_id="test-session",
        mode=MonitoringMode.PASSIVE,
    )


def test_record_serializes_to_dictionary():
    record = make_record()

    data = record.to_dict()

    assert data["component"] == "network"
    assert data["name"] == "wifi_signal"
    assert data["value"] == -58
    assert data["unit"] == "dBm"
    assert data["mode"] == "passive"
    assert data["status"] == "normal"
    assert data["record_type"] == "measurement"


def test_record_round_trip():
    original = make_record()

    serialized = original.to_dict()

    restored = MonitoringRecord.from_dict(serialized)

    assert restored == original


def test_record_has_unique_ids():
    first = make_record()
    second = make_record()

    assert first.record_id != second.record_id


def test_record_has_schema_version():
    record = make_record()

    assert record.schema_version == "1.0"


def test_record_rejects_empty_component():
    with pytest.raises(ValueError):
        MonitoringRecord(
            component="",
            record_type=RecordType.EVENT,
            name="test",
            status=RecordStatus.NORMAL,
            session_id="test-session",
            mode=MonitoringMode.PASSIVE,
        )


def test_record_rejects_empty_session_id():
    with pytest.raises(ValueError):
        MonitoringRecord(
            component="network",
            record_type=RecordType.EVENT,
            name="test",
            status=RecordStatus.NORMAL,
            session_id="",
            mode=MonitoringMode.PASSIVE,
        )


def test_record_is_json_serializable():
    record = make_record()

    encoded = json.dumps(record.to_dict())

    assert json.loads(encoded)["value"] == -58