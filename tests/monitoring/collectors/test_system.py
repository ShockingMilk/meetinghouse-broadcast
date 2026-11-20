import pytest

from pathlib import Path

from broadcast_controller.monitoring.collectors.system import SystemCollector
from broadcast_controller.monitoring.engine import CollectorContext
from broadcast_controller.monitoring.enums import CollectorSafety, MonitoringMode, RecordStatus


def make_context():
    return CollectorContext(
        session_id="test-session",
        mode=MonitoringMode.PASSIVE,
        settings={},
    )


def test_system_collector_is_read_only():
    collector = SystemCollector()

    assert collector.safety is CollectorSafety.READ_ONLY


def test_host_information_is_available():
    collector = SystemCollector()

    records = collector._collect_host(make_context())

    assert len(records) == 1
    assert records[0].name == "host_information"
    assert records[0].value["hostname"]


def test_cpu_first_sample_is_unavailable(tmp_path, monkeypatch):
    import broadcast_controller.monitoring.collectors.system as system_module

    stat_file = tmp_path / "stat"
    stat_file.write_text(
        "cpu 100 20 30 400 10 0 0 0 0 0\n",
        encoding="utf-8",
    )

    collector = SystemCollector(
        proc_stat=stat_file,
        clock=lambda: 10.0,
    )

    monkeypatch.setattr(system_module.platform, "system", lambda: "Linux")

    records = collector._collect_cpu(make_context())

    assert records[0].status is RecordStatus.UNAVAILABLE
    assert "second CPU sample" in records[0].message


def test_cpu_utilization_uses_counter_delta(tmp_path, monkeypatch):
    import broadcast_controller.monitoring.collectors.system as system_module

    stat_file = tmp_path / "stat"

    collector = SystemCollector(
        proc_stat=stat_file,
        clock=lambda: 10.0,
    )

    monkeypatch.setattr(system_module.platform, "system", lambda: "Linux")

    stat_file.write_text(
        "cpu 100 20 30 400 10 0 0 0 0 0\n",
        encoding="utf-8",
    )
    collector._collect_cpu(make_context())

    collector.clock = lambda: 20.0

    stat_file.write_text(
        "cpu 150 20 50 430 10 0 0 0 0 0\n",
        encoding="utf-8",
    )

    records = collector._collect_cpu(make_context())

    assert records[0].status is RecordStatus.NORMAL
    assert records[0].value == pytest.approx(70.0, abs=0.01)


def test_cpu_counter_reset_is_unavailable(tmp_path, monkeypatch):
    import broadcast_controller.monitoring.collectors.system as system_module

    stat_file = tmp_path / "stat"

    current_time = [10.0]

    collector = SystemCollector(
        proc_stat=stat_file,
        clock=lambda: current_time[0],
    )

    monkeypatch.setattr(system_module.platform, "system", lambda: "Linux")

    stat_file.write_text(
        "cpu 100 20 30 400 10 0 0 0 0 0\n",
        encoding="utf-8",
    )
    collector._collect_cpu(make_context())

    current_time[0] = 20.0

    stat_file.write_text(
        "cpu 50 10 20 200 5 0 0 0 0 0\n",
        encoding="utf-8",
    )

    records = collector._collect_cpu(make_context())

    assert records[0].status is RecordStatus.UNAVAILABLE
    assert "reset" in records[0].message


def test_memory_collection(tmp_path, monkeypatch):
    import broadcast_controller.monitoring.collectors.system as system_module

    meminfo = tmp_path / "meminfo"
    meminfo.write_text(
        "MemTotal:       1000 kB\n"
        "MemFree:         200 kB\n"
        "MemAvailable:    400 kB\n",
        encoding="utf-8",
    )

    collector = SystemCollector(proc_meminfo=meminfo)

    monkeypatch.setattr(system_module.platform, "system", lambda: "Linux")

    records = collector._collect_memory(make_context())

    assert records[0].status is RecordStatus.NORMAL
    assert records[0].value["total_bytes"] == 1_024_000
    assert records[0].value["available_bytes"] == 409_600
    assert records[0].value["used_percent"] == 60.0


def test_memory_missing_required_field_is_unavailable(tmp_path, monkeypatch):
    import broadcast_controller.monitoring.collectors.system as system_module

    meminfo = tmp_path / "meminfo"
    meminfo.write_text(
        "MemTotal: 1000 kB\n",
        encoding="utf-8",
    )

    collector = SystemCollector(proc_meminfo=meminfo)

    monkeypatch.setattr(system_module.platform, "system", lambda: "Linux")

    records = collector._collect_memory(make_context())

    assert records[0].status is RecordStatus.UNAVAILABLE


def test_disk_usage_collection(tmp_path):
    collector = SystemCollector(disk_path=tmp_path)

    records = collector._collect_disk(make_context())

    assert records[0].name == "disk_usage"
    assert records[0].status is RecordStatus.NORMAL
    assert records[0].value["total_bytes"] > 0


def test_uptime_collection(tmp_path, monkeypatch):
    import broadcast_controller.monitoring.collectors.system as system_module

    uptime_file = tmp_path / "uptime"
    uptime_file.write_text("12345.67 9876.54\n", encoding="utf-8")

    collector = SystemCollector(proc_uptime=uptime_file)

    monkeypatch.setattr(system_module.platform, "system", lambda: "Linux")

    records = collector._collect_uptime(make_context())

    assert records[0].status is RecordStatus.NORMAL
    assert records[0].value == 12345.67


def test_collect_returns_independent_metric_records(tmp_path, monkeypatch):
    import broadcast_controller.monitoring.collectors.system as system_module

    stat_file = tmp_path / "stat"
    meminfo = tmp_path / "meminfo"
    uptime_file = tmp_path / "uptime"

    stat_file.write_text("cpu 100 20 30 400 10 0 0 0 0 0\n", encoding="utf-8")
    meminfo.write_text(
        "MemTotal: 1000 kB\nMemAvailable: 500 kB\n",
        encoding="utf-8",
    )
    uptime_file.write_text("100.0 50.0\n", encoding="utf-8")

    collector = SystemCollector(
        proc_stat=stat_file,
        proc_meminfo=meminfo,
        proc_uptime=uptime_file,
        disk_path=tmp_path,
    )

    monkeypatch.setattr(system_module.platform, "system", lambda: "Linux")

    records = collector.collect(make_context())
    names = {record.name for record in records}

    assert {
        "host_information",
        "cpu_utilization",
        "memory",
        "disk_usage",
        "uptime",
    }.issubset(names)

    # A first-sample CPU limitation must not prevent other metrics.
    memory_record = next(record for record in records if record.name == "memory")
    disk_record = next(record for record in records if record.name == "disk_usage")

    assert memory_record.status is RecordStatus.NORMAL
    assert disk_record.status is RecordStatus.NORMAL