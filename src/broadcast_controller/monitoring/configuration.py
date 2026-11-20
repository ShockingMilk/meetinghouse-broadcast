from dataclasses import dataclass
from pathlib import Path
from typing import Any

from broadcast_controller.monitoring.enums import MonitoringMode


@dataclass(frozen=True)
class CollectorSettings:
    enabled: bool
    interval_seconds: float
    options: dict[str, Any]


@dataclass(frozen=True)
class MonitoringConfiguration:
    schema_version: str
    output_directory: Path
    max_file_bytes: int
    backup_count: int
    default_mode: MonitoringMode
    modes: dict[str, dict[str, Any]]

    @classmethod
    def from_mapping(
        cls,
        data: dict[str, Any],
        project_root: Path,
    ) -> "MonitoringConfiguration":
        if not isinstance(data, dict):
            raise TypeError("Monitoring configuration must be a dictionary.")

        settings = data.get("monitoring", data)

        if not isinstance(settings, dict):
            raise ValueError("Missing monitoring configuration.")

        schema_version = str(settings.get("schema_version", "1.0"))

        output_directory = Path(settings.get("output_directory", "logs/monitoring"))

        if not output_directory.is_absolute():
            output_directory = Path(project_root) / output_directory

        max_file_bytes = int(settings.get("max_file_bytes", 5 * 1024 * 1024))

        backup_count = int(settings.get("backup_count", 10))

        if max_file_bytes < 1:
            raise ValueError("max_file_bytes must be positive.")

        if backup_count < 1:
            raise ValueError("backup_count must be positive.")

        default_mode = MonitoringMode(settings.get("default_mode", "passive"))

        modes = settings.get("modes", {})

        if not isinstance(modes, dict):
            raise ValueError("Monitoring modes must be a dictionary.")

        for mode in MonitoringMode:
            if mode.value not in modes:
                raise ValueError(f"Missing configuration for mode: {mode.value}")

            mode_settings = modes[mode.value]

            if not isinstance(mode_settings, dict):
                raise ValueError(f"Invalid settings for mode: {mode.value}")

            collectors = mode_settings.get("collectors", {})

            if not isinstance(collectors, dict):
                raise ValueError(f"Invalid collectors for mode: {mode.value}")

            for name, collector in collectors.items():
                if not isinstance(collector, dict):
                    raise ValueError(f"Invalid collector settings: {name}")

                interval = float(collector.get("interval_seconds", 5))

                if interval <= 0:
                    raise ValueError(f"Collector interval must be positive: {name}")

        return cls(
            schema_version=schema_version,
            output_directory=output_directory,
            max_file_bytes=max_file_bytes,
            backup_count=backup_count,
            default_mode=default_mode,
            modes=modes,
        )

    def get_mode_settings(
        self,
        mode: MonitoringMode,
    ) -> dict[str, Any]:
        return self.modes[mode.value]

    def get_collector_settings(
        self,
        mode: MonitoringMode,
        collector_name: str,
    ) -> CollectorSettings:
        mode_settings = self.get_mode_settings(mode)

        collectors = mode_settings.get("collectors", {})

        settings = collectors.get(collector_name, {})

        return CollectorSettings(
            enabled=bool(settings.get("enabled", False)),
            interval_seconds=float(settings.get("interval_seconds", 5)),
            options={
                key: value
                for key, value in settings.items()
                if key not in {"enabled", "interval_seconds"}
            },
        )

    def allows_control_actions(self, mode: MonitoringMode) -> bool:
        # Passive and diagnostic modes are always read-only.
        if mode is not MonitoringMode.ACTIVE:
            return False

        return bool(self.get_mode_settings(mode).get("allow_control_actions", False))