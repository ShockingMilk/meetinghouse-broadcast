import logging

from dataclasses import dataclass, replace
from typing import Protocol

from broadcast_controller.monitoring.configuration import MonitoringConfiguration
from broadcast_controller.monitoring.enums import CollectorSafety, MonitoringMode, RecordStatus, RecordType
from broadcast_controller.monitoring.records import MonitoringRecord
from broadcast_controller.monitoring.session import MonitoringSession
from broadcast_controller.monitoring.writer import JSONLWriter


logger = logging.getLogger("broadcast.monitoring")


@dataclass(frozen=True)
class CollectorContext:
    session_id: str
    mode: MonitoringMode
    settings: dict


class MonitoringCollector(Protocol):
    name: str
    safety: CollectorSafety

    def collect(self, context: CollectorContext) -> list[MonitoringRecord]:
        ...


class MonitoringEngine:
    def __init__(
        self,
        configuration: MonitoringConfiguration,
        session: MonitoringSession,
        writer: JSONLWriter,
    ):
        self.configuration = configuration
        self.session = session
        self.writer = writer

        self._collectors: dict[str, MonitoringCollector] = {}

        self._closed = False

    def register_collector(
        self,
        collector: MonitoringCollector,
    ) -> None:
        if self._closed:
            raise RuntimeError("Cannot register collectors after shutdown.")

        if not collector.name.strip():
            raise ValueError("Collector name cannot be empty.")

        if collector.name in self._collectors:
            raise ValueError(f"Collector already registered: {collector.name}")

        if not isinstance(collector.safety, CollectorSafety):
            raise TypeError("Collectors must declare CollectorSafety.")

        if (
            collector.safety is CollectorSafety.CONTROL
            and not self.configuration.allows_control_actions(self.session.mode)
        ):
            raise PermissionError(f"Collector '{collector.name}' requires control permissions unavailable in this mode.")

        self._collectors[collector.name] = collector

    @property
    def collector_names(self) -> tuple[str, ...]:
        """Return registered collector names in registration order."""
        return tuple(self._collectors)

    def _write_collector_failure(
        self,
        collector_name: str,
        error: Exception,
    ) -> None:
        record = MonitoringRecord(
            component=collector_name,
            record_type=RecordType.DIAGNOSTIC,
            name="collector_execution",
            status=RecordStatus.FAILURE,
            session_id=self.session.session_id,
            mode=self.session.mode,
            message=str(error),
            attributes={
                "error_type": type(error).__name__,
            },
        )

        self.writer.write(record)

        logger.exception(
            "Monitoring collector failed: %s",
            collector_name,
            exc_info=(
                type(error),
                error,
                error.__traceback__,
            ),
        )

    def run_collector(self, name: str) -> int:
        """Run one enabled collector and return the number of records written."""
        if self._closed:
            raise RuntimeError("Monitoring engine is closed.")

        if name not in self._collectors:
            raise KeyError(f"Unknown collector: {name}")

        collector = self._collectors[name]

        settings = self.configuration.get_collector_settings(
            self.session.mode,
            name,
        )

        if not settings.enabled:
            return 0

        if (
            collector.safety is CollectorSafety.CONTROL
            and not self.configuration.allows_control_actions(self.session.mode)
        ):
            raise PermissionError(f"Control collector '{name}' is not allowed.")

        context = CollectorContext(
            session_id=self.session.session_id,
            mode=self.session.mode,
            settings={
                "interval_seconds": settings.interval_seconds,
                **settings.options,
            },
        )

        records_written = 0

        try:
            records = collector.collect(context)

            if records is None:
                records = []

            for record in records:
                if not isinstance(record, MonitoringRecord):
                    raise TypeError(f"Collector '{name}' returned an invalid record.")

                # The engine owns session identity and mode.
                # A collector cannot accidentally write records
                # under a different session or operating mode.
                normalized = replace(
                    record,
                    session_id=self.session.session_id,
                    mode=self.session.mode,
                )

                self.writer.write(normalized)
                records_written += 1

        except Exception as error:
            self._write_collector_failure(name, error)
            records_written += 1

        return records_written

    def run_once(self) -> int:
        """Run every registered collector once."""
        if self._closed:
            raise RuntimeError("Monitoring engine is closed.")

        records_written = 0

        for name in self.collector_names:
            records_written += self.run_collector(name)

        return records_written

    def close(self, status: str = "completed") -> None:
        if self._closed:
            return

        self.session.close(status=status)
        self._closed = True