import json
import pytest

from broadcast_controller.monitoring.enums import MonitoringMode, RecordStatus, RecordType
from broadcast_controller.monitoring.records import MonitoringRecord
from broadcast_controller.monitoring.writer import JSONLWriter


def make_record(name="test_metric"):
    return MonitoringRecord(
        component="test",
        record_type=RecordType.MEASUREMENT,
        name=name,
        value=42,
        status=RecordStatus.NORMAL,
        session_id="test-session",
        mode=MonitoringMode.PASSIVE,
    )


def test_writer_creates_jsonl_file(tmp_path):
    writer = JSONLWriter(tmp_path)

    path = writer.write(make_record())

    assert path.exists()
    assert path.suffix == ".jsonl"


def test_writer_appends_records(tmp_path):
    writer = JSONLWriter(tmp_path)

    writer.write(make_record("first"))
    writer.write(make_record("second"))

    paths = list(tmp_path.glob("records-*.jsonl"))

    assert len(paths) == 1

    lines = paths[0].read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2


def test_writer_outputs_valid_json(tmp_path):
    writer = JSONLWriter(tmp_path)

    writer.write(make_record())

    path = next(tmp_path.glob("records-*.jsonl"))

    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

    assert record["component"] == "test"
    assert record["value"] == 42


def test_writer_rotates_segments(tmp_path):
    writer = JSONLWriter(
        tmp_path,
        max_file_bytes=250,
        backup_count=10,
    )

    for index in range(8):
        writer.write(make_record(f"metric_{index}"))

    paths = sorted(tmp_path.glob("records-*.jsonl"))

    assert len(paths) > 1


def test_writer_enforces_retention(tmp_path):
    writer = JSONLWriter(
        tmp_path,
        max_file_bytes=250,
        backup_count=2,
    )

    for index in range(12):
        writer.write(make_record(f"metric_{index}"))

    paths = list(tmp_path.glob("records-*.jsonl"))

    assert len(paths) <= 2


def test_writer_rejects_invalid_record(tmp_path):
    writer = JSONLWriter(tmp_path)

    with pytest.raises(TypeError):
        writer.write({"not": "a record"})


def test_writer_rejects_invalid_size(tmp_path):
    with pytest.raises(ValueError):
        JSONLWriter(tmp_path, max_file_bytes=0)