"""Read-only network monitoring collector."""

from __future__ import annotations

import json
import logging
import platform
import re
import socket
import subprocess
import time

from pathlib import Path
from typing import Any

from broadcast_controller.monitoring.engine import CollectorContext
from broadcast_controller.monitoring.enums import CollectorSafety, MonitoringMode, RecordStatus, RecordType
from broadcast_controller.monitoring.records import MonitoringRecord


logger = logging.getLogger("broadcast.monitoring.network")


class NetworkCollector:
    """Collect network state without changing network configuration."""

    name = "network"
    safety = CollectorSafety.READ_ONLY

    def __init__(
        self,
        *,
        sys_class_net: Path = Path("/sys/class/net"),
        proc_net_wireless: Path = Path("/proc/net/wireless"),
        resolv_conf: Path = Path("/etc/resolv.conf"),
        command_runner=subprocess.run,
        clock=time.monotonic,
    ) -> None:
        self.sys_class_net = sys_class_net
        self.proc_net_wireless = proc_net_wireless
        self.resolv_conf = resolv_conf
        self.command_runner = command_runner
        self.clock = clock

        self._previous_counters: dict[str, tuple[float, dict[str, int]]] = {}

    def collect(self, context: CollectorContext) -> list[MonitoringRecord]:
        records: list[MonitoringRecord] = []

        records.extend(self._collect_interfaces(context))
        records.extend(self._collect_routes(context))
        records.extend(self._collect_dns_configuration(context))
        records.extend(self._collect_interface_counters(context))
        records.extend(self._collect_wifi(context))

        if context.mode is MonitoringMode.DIAGNOSTIC and context.settings.get("diagnostics_enabled", False):
            records.extend(self._run_connectivity_checks(context))

        return records

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

    def _run_ip_command(self, arguments: list[str]) -> list[dict[str, Any]]:
        """Run a read-only ip command and return its JSON output."""
        try:
            result = self.command_runner(
                ["ip", "-j", *arguments],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )

            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "ip command failed.")

            data = json.loads(result.stdout or "[]")

            if not isinstance(data, list):
                raise ValueError("Unexpected ip command response.")

            return data

        except FileNotFoundError:
            raise RuntimeError("The ip command is not installed.") from None
        except subprocess.TimeoutExpired:
            raise RuntimeError("The ip command timed out.") from None
        except json.JSONDecodeError as error:
            raise RuntimeError("The ip command returned invalid JSON.") from error

    def _collect_interfaces(self, context: CollectorContext) -> list[MonitoringRecord]:
        if platform.system() != "Linux":
            return [
                self._record(
                    context,
                    name="interfaces",
                    status=RecordStatus.UNSUPPORTED,
                    message="Detailed interface inspection is currently implemented for Linux.",
                )
            ]

        try:
            interfaces = self._run_ip_command(["address", "show"])
        except Exception as error:
            return [
                self._record(
                    context,
                    name="interfaces",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                )
            ]

        records: list[MonitoringRecord] = []

        for interface in interfaces:
            name = str(interface.get("ifname", "unknown"))
            flags = interface.get("flags", [])
            operstate = interface.get("operstate", "UNKNOWN")

            addresses = []

            for address in interface.get("addr_info", []):
                local = address.get("local")
                prefix = address.get("prefixlen")

                if local is not None:
                    addresses.append(
                        {
                            "address": local,
                            "prefix_length": prefix,
                            "family": address.get("family"),
                            "scope": address.get("scope"),
                        }
                    )

            records.append(
                self._record(
                    context,
                    name="interface_state",
                    status=RecordStatus.NORMAL,
                    value={
                        "operstate": operstate,
                        "up": "UP" in flags,
                        "flags": flags,
                        "addresses": addresses,
                        "mtu": interface.get("mtu"),
                        "mac_address": interface.get("address"),
                    },
                    attributes={"interface": name},
                    record_type=RecordType.STATUS,
                )
            )

        if not records:
            records.append(
                self._record(
                    context,
                    name="interfaces",
                    status=RecordStatus.UNAVAILABLE,
                    message="No network interfaces were returned.",
                )
            )

        return records

    def _collect_routes(self, context: CollectorContext) -> list[MonitoringRecord]:
        if platform.system() != "Linux":
            return [
                self._record(
                    context,
                    name="default_routes",
                    status=RecordStatus.UNSUPPORTED,
                    message="Route inspection is currently implemented for Linux.",
                )
            ]

        try:
            routes = self._run_ip_command(["route", "show", "default"])
        except Exception as error:
            return [
                self._record(
                    context,
                    name="default_routes",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                )
            ]

        defaults = [
            {
                "gateway": route.get("gateway"),
                "interface": route.get("dev"),
                "metric": route.get("metric"),
                "protocol": route.get("protocol"),
            }
            for route in routes
        ]

        return [
            self._record(
                context,
                name="default_routes",
                status=RecordStatus.NORMAL if defaults else RecordStatus.UNAVAILABLE,
                value=defaults,
                message=None if defaults else "No default route was found.",
            )
        ]

    def _collect_dns_configuration(self, context: CollectorContext) -> list[MonitoringRecord]:
        try:
            content = self.resolv_conf.read_text(encoding="utf-8")
            nameservers = []

            for line in content.splitlines():
                fields = line.split("#", 1)[0].split()

                if len(fields) >= 2 and fields[0] == "nameserver":
                    nameservers.append(fields[1])

            return [
                self._record(
                    context,
                    name="dns_configuration",
                    status=RecordStatus.NORMAL if nameservers else RecordStatus.UNAVAILABLE,
                    value=nameservers,
                    message=None if nameservers else "No nameservers found in resolv.conf.",
                )
            ]

        except OSError as error:
            return [
                self._record(
                    context,
                    name="dns_configuration",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                )
            ]

    def _read_interface_counters(self, interface: str) -> dict[str, int]:
        base = self.sys_class_net / interface / "statistics"

        fields = (
            "rx_bytes",
            "tx_bytes",
            "rx_packets",
            "tx_packets",
            "rx_errors",
            "tx_errors",
            "rx_dropped",
            "tx_dropped",
        )

        counters: dict[str, int] = {}

        for field in fields:
            counters[field] = int((base / field).read_text(encoding="utf-8").strip())

        return counters

    def _collect_interface_counters(self, context: CollectorContext) -> list[MonitoringRecord]:
        if platform.system() != "Linux":
            return [
                self._record(
                    context,
                    name="interface_counters",
                    status=RecordStatus.UNSUPPORTED,
                    message="Interface counters are currently implemented for Linux.",
                )
            ]

        try:
            interfaces = [path.name for path in self.sys_class_net.iterdir() if path.is_dir()]
        except OSError as error:
            return [
                self._record(
                    context,
                    name="interface_counters",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                )
            ]

        records: list[MonitoringRecord] = []

        for interface in interfaces:
            try:
                counters = self._read_interface_counters(interface)
            except (OSError, ValueError) as error:
                records.append(
                    self._record(
                        context,
                        name="interface_counters",
                        status=RecordStatus.UNAVAILABLE,
                        message=str(error),
                        attributes={"interface": interface},
                    )
                )
                continue

            now = self.clock()
            previous = self._previous_counters.get(interface)

            attributes: dict[str, Any] = {"interface": interface}
            rate_status = RecordStatus.NORMAL
            rates: dict[str, float] | None = None

            if previous is None:
                rate_status = RecordStatus.UNAVAILABLE
                attributes["rate_note"] = "Waiting for a second counter sample."
            else:
                previous_time, previous_values = previous
                elapsed = now - previous_time

                if elapsed <= 0:
                    rate_status = RecordStatus.UNAVAILABLE
                    attributes["rate_note"] = "Invalid sample interval."
                elif any(counters[key] < previous_values[key] for key in ("rx_bytes", "tx_bytes")):
                    rate_status = RecordStatus.UNAVAILABLE
                    attributes["rate_note"] = "Counters reset or interface changed."
                else:
                    rates = {
                        "rx_bytes_per_second": (
                            counters["rx_bytes"] - previous_values["rx_bytes"]
                        ) / elapsed,
                        "tx_bytes_per_second": (
                            counters["tx_bytes"] - previous_values["tx_bytes"]
                        ) / elapsed,
                    }

            self._previous_counters[interface] = (now, counters)

            records.append(
                self._record(
                    context,
                    name="interface_counters",
                    status=RecordStatus.NORMAL,
                    value=counters,
                    unit="bytes_and_packets",
                    attributes=attributes,
                )
            )

            records.append(
                self._record(
                    context,
                    name="interface_rates",
                    status=rate_status,
                    value=rates,
                    unit="bytes_per_second",
                    message=attributes.get("rate_note"),
                    attributes={"interface": interface},
                )
            )

        return records

    def _collect_wifi(self, context: CollectorContext) -> list[MonitoringRecord]:
        if platform.system() != "Linux":
            return [
                self._record(
                    context,
                    name="wifi_signal",
                    status=RecordStatus.UNSUPPORTED,
                    message="Wi-Fi signal inspection is currently implemented for Linux.",
                )
            ]

        try:
            lines = self.proc_net_wireless.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return [
                self._record(
                    context,
                    name="wifi_signal",
                    status=RecordStatus.UNAVAILABLE,
                    message="No wireless interface information is available.",
                )
            ]
        except OSError as error:
            return [
                self._record(
                    context,
                    name="wifi_signal",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                )
            ]

        records: list[MonitoringRecord] = []

        for line in lines[2:]:
            if ":" not in line:
                continue

            interface, raw_values = line.split(":", 1)
            values = raw_values.split()

            if len(values) < 3:
                continue

            try:
                link_quality = float(values[1].rstrip("."))
                signal_level = float(values[2].rstrip("."))
            except ValueError:
                continue

            records.append(
                self._record(
                    context,
                    name="wifi_signal",
                    status=RecordStatus.NORMAL,
                    value={
                        "link_quality": link_quality,
                        "signal_level": signal_level,
                    },
                    unit="driver_reported",
                    attributes={"interface": interface.strip()},
                )
            )

        if not records:
            records.append(
                self._record(
                    context,
                    name="wifi_signal",
                    status=RecordStatus.UNAVAILABLE,
                    message="No Wi-Fi signal readings were found.",
                )
            )

        return records

    def _run_connectivity_checks(self, context: CollectorContext) -> list[MonitoringRecord]:
        """Run explicitly configured diagnostic checks.

        These checks generate network traffic and are never run in passive mode.
        """
        records: list[MonitoringRecord] = []

        dns_hosts = context.settings.get("dns_test_hosts", [])
        tcp_targets = context.settings.get("tcp_test_targets", [])
        timeout = float(context.settings.get("connectivity_timeout_seconds", 3))

        if not 0 < timeout <= 10:
            return [
                self._record(
                    context,
                    name="connectivity_configuration",
                    status=RecordStatus.WARNING,
                    message="Connectivity timeout must be greater than 0 and no more than 10 seconds.",
                    record_type=RecordType.DIAGNOSTIC,
                )
            ]

        for host in dns_hosts:
            if not self._valid_host(host):
                records.append(
                    self._record(
                        context,
                        name="dns_resolution",
                        status=RecordStatus.WARNING,
                        message="Invalid DNS test hostname.",
                        attributes={"host": str(host)},
                        record_type=RecordType.DIAGNOSTIC,
                    )
                )
                continue

            started = self.clock()

            try:
                socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
                elapsed = self.clock() - started

                records.append(
                    self._record(
                        context,
                        name="dns_resolution",
                        status=RecordStatus.NORMAL,
                        value=elapsed,
                        unit="seconds",
                        attributes={"host": host},
                        record_type=RecordType.DIAGNOSTIC,
                    )
                )

            except socket.gaierror as error:
                records.append(
                    self._record(
                        context,
                        name="dns_resolution",
                        status=RecordStatus.FAILURE,
                        message=str(error),
                        attributes={"host": host},
                        record_type=RecordType.DIAGNOSTIC,
                    )
                )

        for target in tcp_targets:
            if not isinstance(target, dict):
                continue

            host = target.get("host")
            port = target.get("port")

            if not self._valid_host(host) or not isinstance(port, int) or not 1 <= port <= 65535:
                records.append(
                    self._record(
                        context,
                        name="tcp_connectivity",
                        status=RecordStatus.WARNING,
                        message="Invalid TCP test target.",
                        attributes={"target": str(target)},
                        record_type=RecordType.DIAGNOSTIC,
                    )
                )
                continue

            started = self.clock()

            try:
                with socket.create_connection((host, port), timeout=timeout):
                    elapsed = self.clock() - started

                records.append(
                    self._record(
                        context,
                        name="tcp_connectivity",
                        status=RecordStatus.NORMAL,
                        value=elapsed,
                        unit="seconds",
                        attributes={"host": host, "port": port},
                        record_type=RecordType.DIAGNOSTIC,
                    )
                )

            except OSError as error:
                records.append(
                    self._record(
                        context,
                        name="tcp_connectivity",
                        status=RecordStatus.FAILURE,
                        message=str(error),
                        attributes={"host": host, "port": port},
                        record_type=RecordType.DIAGNOSTIC,
                    )
                )

        return records

    @staticmethod
    def _valid_host(host: Any) -> bool:
        if not isinstance(host, str) or not host or len(host) > 253:
            return False

        if host.strip() != host:
            return False

        if re.fullmatch(r"[A-Za-z0-9.-]+", host) is None:
            return False

        return not host.startswith(".") and not host.endswith(".")