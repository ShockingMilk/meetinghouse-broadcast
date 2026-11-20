import json

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from broadcast_controller.monitoring.enums import MonitoringMode


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class MonitoringSession:
    mode: MonitoringMode
    output_directory: Path

    session_id: str = field(
        default_factory=lambda: (
            datetime.now(timezone.utc).strftime(
                "%Y%m%dT%H%M%SZ"
            )
            + "-"
            + uuid4().hex[:8]
        )
    )

    started_at: str = field(default_factory=_utc_now)
    ended_at: str | None = None

    status: str = "running"

    software_name: str = "meetinghouse-broadcast"
    software_version: str = "0.1.0"
    schema_version: str = "1.0"

    configuration: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.session_id.strip():
            raise ValueError("Session ID cannot be empty.")

        self.output_directory = Path(self.output_directory)

        self.session_directory.mkdir(parents=True, exist_ok=True)

        self.write_metadata()

    @property
    def session_directory(self) -> Path:
        return self.output_directory / self.session_id

    @property
    def metadata_path(self) -> Path:
        return self.session_directory / "session.json"

    def write_metadata(self) -> None:
        metadata = asdict(self)

        metadata["mode"] = self.mode.value
        metadata["output_directory"] = str(self.output_directory)

        temporary_path = self.metadata_path.with_suffix(".json.tmp")

        temporary_path.write_text(
            json.dumps(
                metadata,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        temporary_path.replace(self.metadata_path)

    def close(self, status: str = "completed") -> None:
        if self.ended_at is not None:
            return

        self.ended_at = _utc_now()
        self.status = status

        self.write_metadata()