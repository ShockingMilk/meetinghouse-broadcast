from unittest.mock import Mock

import pytest

from broadcast_controller.monitoring.collectors.camera import CameraCollector
from broadcast_controller.monitoring.engine import CollectorContext
from broadcast_controller.monitoring.enums import CollectorSafety, MonitoringMode, RecordStatus


@pytest.fixture
def config():
    return {
        "camera": {
            "camera": {
                "enabled": True,
                "name": "Tongveo NV20U-4K",
                "connection": {
                    "host": "192.168.109.206",
                    "port": 52381,
                    "transport": "udp",
                    "packet_mode": "visca_over_ip",
                    "timeout": 1.0,
                },
            }
        }
    }


def make_context(mode=MonitoringMode.PASSIVE, settings=None):
    return CollectorContext(
        session_id="test-session",
        mode=mode,
        settings=settings or {},
    )


def test_camera_collector_is_read_only(config):
    collector = CameraCollector(config)

    assert collector.safety is CollectorSafety.READ_ONLY


def test_passive_collection_does_not_probe_camera(config):
    connection_factory = Mock()

    collector = CameraCollector(
        config,
        connection_factory=connection_factory,
    )

    records = collector.collect(
        make_context(
            MonitoringMode.PASSIVE,
            {
                "rtsp_tcp_probe_enabled": True,
                "rtsp_host": "192.168.109.206",
                "rtsp_port": 554,
            },
        )
    )

    connection_factory.assert_not_called()

    reachability = next(
        record for record in records
        if record.name == "camera_reachability"
    )

    assert reachability.status is RecordStatus.UNAVAILABLE
    assert "No VISCA packet was sent" in reachability.message


def test_camera_configuration_is_recorded_without_secrets(config):
    collector = CameraCollector(config)

    records = collector.collect(make_context())
    configuration = next(
        record for record in records
        if record.name == "camera_configuration"
    )

    assert configuration.status is RecordStatus.NORMAL
    assert configuration.value["host"] == "192.168.109.206"
    assert configuration.value["port"] == 52381
    assert "password" not in configuration.value
    assert "commands" not in configuration.value


def test_disabled_camera_is_reported(config):
    config["camera"]["camera"]["enabled"] = False

    collector = CameraCollector(config)
    records = collector.collect(make_context())

    reachability = next(
        record for record in records
        if record.name == "camera_reachability"
    )

    assert reachability.status is RecordStatus.UNSUPPORTED
    assert "disabled" in reachability.message


def test_diagnostic_tcp_check_requires_explicit_configuration(config):
    connection_factory = Mock()

    collector = CameraCollector(
        config,
        connection_factory=connection_factory,
    )

    records = collector.collect(
        make_context(
            MonitoringMode.DIAGNOSTIC,
            {
                "rtsp_tcp_probe_enabled": True,
                "rtsp_host": "",
                "rtsp_port": None,
            },
        )
    )

    connection_factory.assert_not_called()

    check = next(
        record for record in records
        if record.name == "rtsp_tcp_listener"
    )

    assert check.status is RecordStatus.WARNING


def test_diagnostic_tcp_check_succeeds(config):
    connection = Mock()
    connection_factory = Mock(return_value=connection)

    collector = CameraCollector(
        config,
        connection_factory=connection_factory,
    )

    records = collector.collect(
        make_context(
            MonitoringMode.DIAGNOSTIC,
            {
                "rtsp_tcp_probe_enabled": True,
                "rtsp_host": "192.168.109.206",
                "rtsp_port": 554,
                "connectivity_timeout_seconds": 3,
            },
        )
    )

    connection_factory.assert_called_once_with(
        ("192.168.109.206", 554),
        timeout=3,
    )
    connection.close.assert_called_once()

    check = next(
        record for record in records
        if record.name == "rtsp_tcp_listener"
    )

    assert check.status is RecordStatus.NORMAL
    assert "does not verify RTSP video" in check.message


def test_diagnostic_tcp_check_failure_is_recorded(config):
    connection_factory = Mock(
        side_effect=ConnectionRefusedError("Connection refused")
    )

    collector = CameraCollector(
        config,
        connection_factory=connection_factory,
    )

    records = collector.collect(
        make_context(
            MonitoringMode.DIAGNOSTIC,
            {
                "rtsp_tcp_probe_enabled": True,
                "rtsp_host": "192.168.109.206",
                "rtsp_port": 554,
                "connectivity_timeout_seconds": 3,
            },
        )
    )

    check = next(
        record for record in records
        if record.name == "rtsp_tcp_listener"
    )

    assert check.status is RecordStatus.FAILURE
    assert "Connection refused" in check.message


def test_invalid_tcp_port_is_rejected(config):
    connection_factory = Mock()

    collector = CameraCollector(
        config,
        connection_factory=connection_factory,
    )

    records = collector.collect(
        make_context(
            MonitoringMode.DIAGNOSTIC,
            {
                "rtsp_tcp_probe_enabled": True,
                "rtsp_host": "192.168.109.206",
                "rtsp_port": 70000,
            },
        )
    )

    connection_factory.assert_not_called()

    check = next(
        record for record in records
        if record.name == "rtsp_tcp_listener"
    )

    assert check.status is RecordStatus.WARNING