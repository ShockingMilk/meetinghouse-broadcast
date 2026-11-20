import json

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TestStatus(str, Enum):
    __test__ = False

    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class TestResult:
    __test__ = False

    test_name: str
    status: TestStatus
    message: str
    details: dict = field(default_factory=dict)

    result_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.test_name.strip():
            raise ValueError("Test name cannot be empty.")

        if not isinstance(self.status, TestStatus):
            raise TypeError("Invalid test status.")

        if not isinstance(self.details, dict):
            raise TypeError("Test details must be a dictionary.")

    def to_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        return data


class TestResultWriter:
    """Write test events and results to a dedicated session directory."""
    __test__ = False

    def __init__(self, output_directory: Path):
        self.session_id = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid4().hex[:8]
        )

        self.session_directory = Path(output_directory) / self.session_id

        self.session_directory.mkdir(
            parents=True,
            exist_ok=False,
        )

        self.events_path = self.session_directory / "events.jsonl"
        self.results_path = self.session_directory / "results.jsonl"
        self.metadata_path = self.session_directory / "session.json"

        self._lock = Lock()
        self._closed = False

        self._metadata = {
            "session_id": self.session_id,
            "started_at": utc_now(),
            "ended_at": None,
            "status": "running",
            "software_name": "meetinghouse-broadcast",
            "schema_version": "1.0",
        }

        self._write_metadata()

    def _append_jsonl(self, path: Path, data: dict) -> None:
        serialized = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

        with self._lock:
            if self._closed:
                raise RuntimeError("Test session is closed.")

            with path.open("a", encoding="utf-8") as file:
                file.write(serialized + "\n")
                file.flush()

    def _write_metadata(self) -> None:
        temporary = self.metadata_path.with_suffix(".json.tmp")

        temporary.write_text(
            json.dumps(
                self._metadata,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        temporary.replace(self.metadata_path)

    def write_event(self, event) -> None:
        self._append_jsonl(
            self.events_path,
            event.to_dict(),
        )

    def write_result(self, result: TestResult) -> None:
        self._append_jsonl(
            self.results_path,
            result.to_dict(),
        )

    def close(self, status: str = "completed") -> None:
        with self._lock:
            if self._closed:
                return

            self._metadata["ended_at"] = utc_now()
            self._metadata["status"] = status

            self._write_metadata()
            self._closed = True