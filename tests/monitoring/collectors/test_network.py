import json
import pytest
import subprocess

from pathlib import Path
from types import SimpleNamespace


from broadcast_controller.monitoring.collectors.network import NetworkCollector
from broadcast_controller.monitoring.engine import CollectorContext
from broadcast_controller.monitoring.enums import CollectorSafety, MonitoringMode, RecordStatus


def make_context(
    mode=MonitoringMode.PASSIVE,
    settings=None,
):
    return CollectorContext(
        session_id="test-session",
        mode=mode,
        settings=settings or {},
    )


def test_network_collector_is_read_only():
    collector = NetworkCollector()

    assert collector.safety is CollectorSafety.READ_ONLY


def test_passive_mode_does_not_run_connectivity_probes(monkeypatch):
    import broadcast_controller.monitoring.collectors.network as network_module

    def unexpected_probe(*args, **kwargs):
        raise AssertionError("Passive mode must not initiate connectivity probes.")

    monkeypatch.setattr(network_module.socket, "getaddrinfo", unexpected_probe)
    monkeypatch.setattr(network_module.socket, "create_connection", unexpected_probe)

    collector = NetworkCollector(
        sys_class_net=Path("/does-not-exist"),
        proc_net_wireless=Path("/does-not-exist"),
        resolv_conf=Path("/does-not-exist"),
    )

    monkeypatch.setattr(network_module.platform, "system", lambda: "Other")

    records = collector.collect(
        make_context(
            MonitoringMode.PASSIVE,
            {
                "diagnostics_enabled": True,
                "dns_test_hosts": ["example.com"],
                "tcp_test_targets": [{"host": "example.com", "port": 443}],
            },
        )
    )

    assert records
    assert not any(record.name in {"dns_resolution", "tcp_connectivity"} for record in records)


def test_interface_command_parses_json(monkeypatch):
    import broadcast_controller.monitoring.collectors.network as network_module

    response = [
        {
            "ifname": "eth0",
            "flags": ["UP", "BROADCAST"],
            "operstate": "UP",
            "mtu": 1500,
            "address": "00:11:22:33:44:55",
            "addr_info": [
                {
                    "family": "inet",
                    "local": "192.168.1.20",
                    "prefixlen": 24,
                    "scope": "global",
                }
            ],
        }
    ]

    def runner(command, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(response),
            stderr="",
        )

    collector = NetworkCollector(command_runner=runner)
    monkeypatch.setattr(network_module.platform, "system", lambda: "Linux")

    records = collector._collect_interfaces(make_context())

    assert len(records) == 1
    assert records[0].name == "interface_state"
    assert records[0].attributes["interface"] == "eth0"
    assert records[0].value["addresses"][0]["address"] == "192.168.1.20"


def test_interface_command_failure_is_unavailable(monkeypatch):
    import broadcast_controller.monitoring.collectors.network as network_module

    def runner(command, **kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="permission denied",
        )

    collector = NetworkCollector(command_runner=runner)
    monkeypatch.setattr(network_module.platform, "system", lambda: "Linux")

    records = collector._collect_interfaces(make_context())

    assert records[0].status is RecordStatus.UNAVAILABLE
    assert "permission denied" in records[0].message


def test_dns_configuration_reads_nameservers(tmp_path):
    resolv_conf = tmp_path / "resolv.conf"
    resolv_conf.write_text(
        "search local\n"
        "nameserver 192.168.1.1\n"
        "nameserver 1.1.1.1\n",
        encoding="utf-8",
    )

    collector = NetworkCollector(resolv_conf=resolv_conf)

    records = collector._collect_dns_configuration(make_context())

    assert records[0].value == ["192.168.1.1", "1.1.1.1"]
    assert records[0].status is RecordStatus.NORMAL


def create_interface_counters(root: Path, interface: str, values: dict):
    statistics = root / interface / "statistics"
    statistics.mkdir(parents=True)

    for name, value in values.items():
        (statistics / name).write_text(str(value), encoding="utf-8")


def test_interface_rate_requires_two_samples(tmp_path, monkeypatch):
    import broadcast_controller.monitoring.collectors.network as network_module

    values = {
        "rx_bytes": 1000,
        "tx_bytes": 2000,
        "rx_packets": 10,
        "tx_packets": 20,
        "rx_errors": 0,
        "tx_errors": 0,
        "rx_dropped": 0,
        "tx_dropped": 0,
    }

    create_interface_counters(tmp_path, "eth0", values)

    current_time = [10.0]

    collector = NetworkCollector(
        sys_class_net=tmp_path,
        clock=lambda: current_time[0],
    )

    monkeypatch.setattr(network_module.platform, "system", lambda: "Linux")

    first = collector._collect_interface_counters(make_context())
    first_rate = next(record for record in first if record.name == "interface_rates")

    assert first_rate.status is RecordStatus.UNAVAILABLE

    updated = dict(values)
    updated["rx_bytes"] = 2000
    updated["tx_bytes"] = 3000

    for name, value in updated.items():
        (tmp_path / "eth0" / "statistics" / name).write_text(
            str(value),
            encoding="utf-8",
        )

    current_time[0] = 20.0

    second = collector._collect_interface_counters(make_context())
    second_rate = next(record for record in second if record.name == "interface_rates")

    assert second_rate.status is RecordStatus.NORMAL
    assert second_rate.value["rx_bytes_per_second"] == 100
    assert second_rate.value["tx_bytes_per_second"] == 100


def test_interface_counter_reset_does_not_create_negative_rate(tmp_path, monkeypatch):
    import broadcast_controller.monitoring.collectors.network as network_module

    values = {
        "rx_bytes": 1000,
        "tx_bytes": 2000,
        "rx_packets": 10,
        "tx_packets": 20,
        "rx_errors": 0,
        "tx_errors": 0,
        "rx_dropped": 0,
        "tx_dropped": 0,
    }

    create_interface_counters(tmp_path, "eth0", values)

    current_time = [10.0]

    collector = NetworkCollector(
        sys_class_net=tmp_path,
        clock=lambda: current_time[0],
    )

    monkeypatch.setattr(network_module.platform, "system", lambda: "Linux")

    collector._collect_interface_counters(make_context())

    reset_values = dict(values)
    reset_values["rx_bytes"] = 100
    reset_values["tx_bytes"] = 100

    for name, value in reset_values.items():
        (tmp_path / "eth0" / "statistics" / name).write_text(
            str(value),
            encoding="utf-8",
        )

    current_time[0] = 20.0

    records = collector._collect_interface_counters(make_context())
    rate = next(record for record in records if record.name == "interface_rates")

    assert rate.status is RecordStatus.UNAVAILABLE
    assert rate.value is None


def test_diagnostic_mode_runs_explicit_dns_check(monkeypatch):
    import broadcast_controller.monitoring.collectors.network as network_module

    monkeypatch.setattr(
        network_module.platform,
        "system",
        lambda: "Other",
    )

    monkeypatch.setattr(
        network_module.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 0))],
    )

    collector = NetworkCollector()

    records = collector._run_connectivity_checks(
        make_context(
            MonitoringMode.DIAGNOSTIC,
            {
                "diagnostics_enabled": True,
                "dns_test_hosts": ["example.com"],
                "connectivity_timeout_seconds": 2,
            },
        )
    )

    assert len(records) == 1
    assert records[0].name == "dns_resolution"
    assert records[0].status is RecordStatus.NORMAL


def test_invalid_diagnostic_hostname_is_rejected():
    collector = NetworkCollector()

    records = collector._run_connectivity_checks(
        make_context(
            MonitoringMode.DIAGNOSTIC,
            {
                "dns_test_hosts": ["bad hostname"],
            },
        )
    )

    assert records[0].status is RecordStatus.WARNING