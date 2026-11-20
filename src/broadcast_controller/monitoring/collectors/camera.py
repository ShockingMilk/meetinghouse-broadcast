"""Read-only camera monitoring collector."""

from __future__ import annotations

import logging
import socket

from typing import Any

from broadcast_controller.monitoring.engine import CollectorContext
from broadcast_controller.monitoring.enums import CollectorSafety, MonitoringMode, RecordStatus, RecordType
from broadcast_controller.monitoring.records import MonitoringRecord


logger = logging.getLogger("broadcast.monitoring.camera")


class CameraCollector:
    """Collect camera configuration and optional diagnostic reachability."""

    name = "camera"
    safety = CollectorSafety.READ_ONLY

    def __init__(
        self,
        config: dict,
        connection_factory=socket.create_connection,
    ) -> None:
        self.config = config["camera"]["camera"]
        self.connection_factory = connection_factory

    def _record(
        self,
        context: CollectorContext,
        *,
        name: str,
        status: RecordStatus,
        value: Any = None,
        unit: str | None = None,
        message: str | None = None,
        attributes: dict[str, Any] | None = None,
        record_type: RecordType = RecordType.MEASUREMENT,
    ) -> MonitoringRecord:
        return MonitoringRecord(
            component=self.name,
            record_type=record_type,
            name=name,
            status=status,
            session_id=context.session_id,
            mode=context.mode,
            value=value,
            unit=unit,
            message=message,
            attributes=attributes or {},
        )

    def collect(self, context: CollectorContext) -> list[MonitoringRecord]:
        records = self._collect_configuration(context)

        if not self.config.get("enabled", False):
            records.append(
                self._record(
                    context,
                    name="camera_reachability",
                    status=RecordStatus.UNSUPPORTED,
                    message="Camera integration is disabled.",
                    record_type=RecordType.STATUS,
                )
            )
            return records

        if (
            context.mode is MonitoringMode.DIAGNOSTIC
            and context.settings.get("rtsp_tcp_probe_enabled", False)
        ):
            records.extend(self._run_rtsp_tcp_check(context))
        else:
            records.append(
                self._record(
                    context,
                    name="camera_reachability",
                    status=RecordStatus.UNAVAILABLE,
                    message=(
                        "Camera reachability has not been verified. "
                        "The configured VISCA transport is UDP and does not "
                        "provide a safe passive status query. No VISCA "
                        "packet was sent."
                    ),
                    record_type=RecordType.STATUS,
                )
            )

        return records

    def _collect_configuration(
        self,
        context: CollectorContext,
    ) -> list[MonitoringRecord]:
        connection = self.config.get("connection", {})

        # Only non-secret configuration fields are recorded.
        value = {
            "enabled": bool(self.config.get("enabled", False)),
            "name": self.config.get("name"),
            "host": connection.get("host"),
            "port": connection.get("port"),
            "transport": connection.get("transport"),
            "packet_mode": connection.get("packet_mode"),
        }

        return [
            self._record(
                context,
                name="camera_configuration",
                status=RecordStatus.NORMAL,
                value=value,
                record_type=RecordType.STATUS,
            )
        ]

    def _run_rtsp_tcp_check(
        self,
        context: CollectorContext,
    ) -> list[MonitoringRecord]:
        """Check whether a configured RTSP TCP port accepts connections.

        This does not send an RTSP request, retrieve video, or issue VISCA.
        It is diagnostic-only because it creates a network connection.
        """
        host = context.settings.get("rtsp_host")
        port = context.settings.get("rtsp_port")
        timeout = context.settings.get("connectivity_timeout_seconds", 3)

        if not isinstance(host, str) or not host.strip():
            return [
                self._record(
                    context,
                    name="rtsp_tcp_listener",
                    status=RecordStatus.WARNING,
                    message="No RTSP host is configured for the diagnostic check.",
                    record_type=RecordType.DIAGNOSTIC,
                )
            ]

        if not isinstance(port, int) or not 1 <= port <= 65535:
            return [
                self._record(
                    context,
                    name="rtsp_tcp_listener",
                    status=RecordStatus.WARNING,
                    message="A valid RTSP TCP port is required.",
                    attributes={"host": host},
                    record_type=RecordType.DIAGNOSTIC,
                )
            ]

        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 10:
            return [
                self._record(
                    context,
                    name="rtsp_tcp_listener",
                    status=RecordStatus.WARNING,
                    message="Connectivity timeout must be greater than 0 and no more than 10 seconds.",
                    attributes={"host": host, "port": port},
                    record_type=RecordType.DIAGNOSTIC,
                )
            ]

        try:
            connection = self.connection_factory(
                (host, port),
                timeout=timeout,
            )

            try:
                return [
                    self._record(
                        context,
                        name="rtsp_tcp_listener",
                        status=RecordStatus.NORMAL,
                        value=True,
                        message=(
                            "TCP connection succeeded. This confirms only "
                            "that a listener accepted the connection; it "
                            "does not verify RTSP video."
                        ),
                        attributes={"host": host, "port": port},
                        record_type=RecordType.DIAGNOSTIC,
                    )
                ]
            finally:
                connection.close()

        except OSError as error:
            return [
                self._record(
                    context,
                    name="rtsp_tcp_listener",
                    status=RecordStatus.FAILURE,
                    value=False,
                    message=str(error),
                    attributes={"host": host, "port": port},
                    record_type=RecordType.DIAGNOSTIC,
                )
            ]