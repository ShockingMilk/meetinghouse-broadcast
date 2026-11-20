import json
import threading

from pathlib import Path

from broadcast_controller.monitoring.records import MonitoringRecord


class JSONLWriter:
    def __init__(
        self,
        session_directory: Path,
        max_file_bytes: int = 5 * 1024 * 1024,
        backup_count: int = 10,
    ):
        if max_file_bytes < 1:
            raise ValueError("Maximum file size must be positive.")

        if backup_count < 1:
            raise ValueError("Backup count must be positive.")

        self.session_directory = Path(session_directory)

        self.session_directory.mkdir(parents=True, exist_ok=True)

        self.max_file_bytes = max_file_bytes
        self.backup_count = backup_count

        self._lock = threading.Lock()

    def _segment_paths(self) -> list[Path]:
        return sorted(self.session_directory.glob("records-*.jsonl"))

    def _next_segment(self) -> Path:
        paths = self._segment_paths()

        if not paths:
            return self.session_directory / "records-0001.jsonl"

        current = paths[-1]

        if current.stat().st_size < self.max_file_bytes:
            return current

        number = int(current.stem.split("-")[-1])

        return self.session_directory / f"records-{number + 1:04d}.jsonl"

    def _enforce_retention(self) -> None:
        paths = self._segment_paths()

        while len(paths) > self.backup_count:
            oldest = paths.pop(0)
            oldest.unlink(missing_ok=True)

    def write(self, record: MonitoringRecord) -> Path:
        if not isinstance(record, MonitoringRecord):
            raise TypeError("Only MonitoringRecord objects can be written.")

        serialized = json.dumps(
            record.to_dict(),
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        )

        line = serialized + "\n"
        encoded_size = len(line.encode("utf-8"))

        with self._lock:
            path = self._next_segment()

            if (
                path.exists()
                and path.stat().st_size > 0
                and path.stat().st_size + encoded_size > self.max_file_bytes
            ):
                number = int(path.stem.split("-")[-1])

                path = self.session_directory / f"records-{number + 1:04d}.jsonl"

            with path.open("a", encoding="utf-8") as file:
                file.write(line)
                file.flush()

            self._enforce_retention()

            return path