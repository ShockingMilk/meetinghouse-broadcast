from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class HarnessEventType(str, Enum):
    HARNESS_STARTED = "harness_started"
    OBS_CONNECTED = "obs_connected"
    CAMERA_PRESET_REQUESTED = "camera_preset_requested"
    SCENE_TRANSITION_REQUESTED = "scene_transition_requested"
    RTSP_INTERRUPTION_REQUESTED = "rtsp_interruption_requested"
    RTSP_RESTORATION_REQUESTED = "rtsp_restoration_requested"
    HARNESS_STOPPED = "harness_stopped"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class HarnessEvent:
    event_type: HarnessEventType
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now)
    event_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self):
        if not isinstance(self.event_type, HarnessEventType):
            raise TypeError("Invalid harness event type.")

        if not isinstance(self.payload, dict):
            raise TypeError("Event payload must be a dictionary.")

        if not self.event_id.strip():
            raise ValueError("Event ID cannot be empty.")

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }