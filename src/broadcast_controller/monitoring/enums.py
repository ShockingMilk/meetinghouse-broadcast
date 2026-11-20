from enum import Enum


class MonitoringMode(str, Enum):
    PASSIVE = "passive"
    ACTIVE = "active"
    DIAGNOSTIC = "diagnostic"


class RecordType(str, Enum):
    MEASUREMENT = "measurement"
    EVENT = "event"
    STATUS = "status"
    DIAGNOSTIC = "diagnostic"


class RecordStatus(str, Enum):
    NORMAL = "normal"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    WARNING = "warning"
    DEGRADED = "degraded"
    FAILURE = "failure"


class CollectorSafety(str, Enum):
    READ_ONLY = "read_only"
    CONTROL = "control"