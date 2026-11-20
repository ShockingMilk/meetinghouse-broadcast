from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from broadcast_controller.monitoring.enums import MonitoringMode, RecordStatus, RecordType


SCHEMA_VERSION = "1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class MonitoringRecord:
    component: str
    record_type: RecordType
    name: str
    status: RecordStatus

    session_id: str
    mode: MonitoringMode

    value: Any = None
    unit: str | None = None
    message: str | None = None

    attributes: dict[str, Any] = field(default_factory=dict)

    timestamp: str = field(default_factory=utc_now)
    record_id: str = field(default_factory=lambda: str(uuid4()))

    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        if not self.component.strip():
            raise ValueError("Component cannot be empty.")

        if not self.name.strip():
            raise ValueError("Record name cannot be empty.")

        if not self.session_id.strip():
            raise ValueError("Session ID cannot be empty.")

        if not self.record_id.strip():
            raise ValueError("Record ID cannot be empty.")

        if not self.schema_version.strip():
            raise ValueError("Schema version cannot be empty.")

        if not isinstance(self.attributes, dict):
            raise TypeError("Attributes must be a dictionary.")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)

        data["record_type"] = self.record_type.value
        data["status"] = self.status.value
        data["mode"] = self.mode.value

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MonitoringRecord":
        values = dict(data)

        values["record_type"] = RecordType(values["record_type"])
        values["status"] = RecordStatus(values["status"])
        values["mode"] = MonitoringMode(values["mode"])

        return cls(**values)