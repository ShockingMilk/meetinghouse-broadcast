"""Read-only system monitoring collector."""

from __future__ import annotations

import os
import platform
import shutil
import time

from pathlib import Path
from typing import Any

from broadcast_controller.monitoring.engine import CollectorContext
from broadcast_controller.monitoring.enums import CollectorSafety, RecordStatus, RecordType
from broadcast_controller.monitoring.records import MonitoringRecord


class SystemCollector:
    """Collect host resource and operating-system information."""

    name = "system"
    safety = CollectorSafety.READ_ONLY

    def __init__(
        self,
        *,
        proc_stat: Path = Path("/proc/stat"),
        proc_meminfo: Path = Path("/proc/meminfo"),
        proc_uptime: Path = Path("/proc/uptime"),
        disk_path: Path = Path("/"),
        clock=time.monotonic,
    ) -> None:
        self.proc_stat = proc_stat
        self.proc_meminfo = proc_meminfo
        self.proc_uptime = proc_uptime
        self.disk_path = disk_path
        self.clock = clock

        self._previous_cpu: tuple[float, list[int]] | None = None

    def collect(self, context: CollectorContext) -> list[MonitoringRecord]:
        records: list[MonitoringRecord] = []

        records.extend(self._collect_host(context))
        records.extend(self._collect_cpu(context))
        records.extend(self._collect_memory(context))
        records.extend(self._collect_disk(context))
        records.extend(self._collect_uptime(context))

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

    def _collect_host(self, context: CollectorContext) -> list[MonitoringRecord]:
        value = {
            "hostname": platform.node(),
            "operating_system": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "processor": platform.processor() or None,
            "logical_cpu_count": os.cpu_count(),
            "python_version": platform.python_version(),
        }

        return [
            self._record(
                context,
                name="host_information",
                status=RecordStatus.NORMAL,
                value=value,
                record_type=RecordType.STATUS,
            )
        ]

    def _read_cpu_counters(self) -> list[int]:
        """Read aggregate CPU counters from Linux /proc/stat."""
        with self.proc_stat.open("r", encoding="utf-8") as file:
            for line in file:
                fields = line.split()

                if fields and fields[0] == "cpu":
                    return [int(value) for value in fields[1:]]

        raise ValueError("Aggregate CPU counters were not found.")

    def _collect_cpu(self, context: CollectorContext) -> list[MonitoringRecord]:
        if platform.system() != "Linux":
            return [
                self._record(
                    context,
                    name="cpu_utilization",
                    status=RecordStatus.UNSUPPORTED,
                    message="CPU utilization sampling is currently implemented for Linux.",
                )
            ]

        try:
            counters = self._read_cpu_counters()

            if len(counters) < 4:
                raise ValueError("Insufficient CPU counter fields.")

            now = self.clock()
            previous = self._previous_cpu
            self._previous_cpu = (now, counters)

            if previous is None:
                return [
                    self._record(
                        context,
                        name="cpu_utilization",
                        status=RecordStatus.UNAVAILABLE,
                        message="Waiting for a second CPU sample.",
                    )
                ]

            previous_time, previous_counters = previous
            elapsed = now - previous_time

            if elapsed <= 0:
                return [
                    self._record(
                        context,
                        name="cpu_utilization",
                        status=RecordStatus.UNAVAILABLE,
                        message="Invalid CPU sample interval.",
                    )
                ]

            if len(previous_counters) != len(counters):
                return [
                    self._record(
                        context,
                        name="cpu_utilization",
                        status=RecordStatus.UNAVAILABLE,
                        message="CPU counter layout changed between samples.",
                    )
                ]

            deltas = [current - old for current, old in zip(counters, previous_counters)]

            if any(delta < 0 for delta in deltas):
                return [
                    self._record(
                        context,
                        name="cpu_utilization",
                        status=RecordStatus.UNAVAILABLE,
                        message="CPU counters reset between samples.",
                    )
                ]

            total_delta = sum(deltas)

            if total_delta <= 0:
                return [
                    self._record(
                        context,
                        name="cpu_utilization",
                        status=RecordStatus.UNAVAILABLE,
                        message="No CPU counter progress was observed.",
                    )
                ]

            # Linux CPU fields:
            # user, nice, system, idle, iowait, irq, softirq, steal,
            # guest, guest_nice
            idle_delta = deltas[3]

            if len(deltas) > 4:
                idle_delta += deltas[4]

            # Guest time is already included in user/nice.
            # Subtract it to avoid double counting.
            if len(deltas) > 8:
                total_delta -= deltas[8]

            if len(deltas) > 9:
                total_delta -= deltas[9]

            busy_delta = max(0, total_delta - idle_delta)
            utilization = (busy_delta / total_delta) * 100

            return [
                self._record(
                    context,
                    name="cpu_utilization",
                    status=RecordStatus.NORMAL,
                    value=round(utilization, 2),
                    unit="percent",
                    attributes={"sample_interval_seconds": elapsed},
                )
            ]

        except (OSError, ValueError) as error:
            return [
                self._record(
                    context,
                    name="cpu_utilization",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                )
            ]

    def _collect_memory(self, context: CollectorContext) -> list[MonitoringRecord]:
        if platform.system() != "Linux":
            return [
                self._record(
                    context,
                    name="memory",
                    status=RecordStatus.UNSUPPORTED,
                    message="Memory inspection is currently implemented for Linux.",
                )
            ]

        try:
            values: dict[str, int] = {}

            for line in self.proc_meminfo.read_text(encoding="utf-8").splitlines():
                fields = line.split()

                if len(fields) >= 2:
                    key = fields[0].rstrip(":")
                    try:
                        values[key] = int(fields[1]) * 1024
                    except ValueError:
                        continue

            total = values.get("MemTotal")
            available = values.get("MemAvailable")

            if total is None or available is None or total <= 0:
                raise ValueError("Required memory fields were not found.")

            used = total - available

            return [
                self._record(
                    context,
                    name="memory",
                    status=RecordStatus.NORMAL,
                    value={
                        "total_bytes": total,
                        "available_bytes": available,
                        "used_bytes": used,
                        "used_percent": round((used / total) * 100, 2),
                    },
                    unit="bytes",
                )
            ]

        except (OSError, ValueError) as error:
            return [
                self._record(
                    context,
                    name="memory",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                )
            ]

    def _collect_disk(self, context: CollectorContext) -> list[MonitoringRecord]:
        try:
            usage = shutil.disk_usage(self.disk_path)

            if usage.total <= 0:
                raise ValueError("Disk total capacity is zero.")

            used_percent = (usage.used / usage.total) * 100

            return [
                self._record(
                    context,
                    name="disk_usage",
                    status=RecordStatus.NORMAL,
                    value={
                        "path": str(self.disk_path),
                        "total_bytes": usage.total,
                        "used_bytes": usage.used,
                        "free_bytes": usage.free,
                        "used_percent": round(used_percent, 2),
                    },
                    unit="bytes",
                )
            ]

        except (OSError, ValueError) as error:
            return [
                self._record(
                    context,
                    name="disk_usage",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                )
            ]

    def _collect_uptime(self, context: CollectorContext) -> list[MonitoringRecord]:
        if platform.system() != "Linux":
            return [
                self._record(
                    context,
                    name="uptime",
                    status=RecordStatus.UNSUPPORTED,
                    message="Uptime inspection is currently implemented for Linux.",
                )
            ]

        try:
            raw_value = self.proc_uptime.read_text(encoding="utf-8").split()[0]
            uptime_seconds = float(raw_value)

            return [
                self._record(
                    context,
                    name="uptime",
                    status=RecordStatus.NORMAL,
                    value=round(uptime_seconds, 2),
                    unit="seconds",
                )
            ]

        except (OSError, ValueError, IndexError) as error:
            return [
                self._record(
                    context,
                    name="uptime",
                    status=RecordStatus.UNAVAILABLE,
                    message=str(error),
                )
            ]