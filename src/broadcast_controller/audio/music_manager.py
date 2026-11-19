import logging
import random
import subprocess
import threading

from pathlib import Path

class MusicManager:
    SUPPORTED_EXTENSIONS = {
        ".mp3",
        ".wav",
        ".ogg",
        ".flac",
    }

    def __init__(self, config, sink_name, project_root):
        self.config = config["audio"]["audio"]
        self.music_config = self.config["music"]

        self.logger = logging.getLogger("broadcast.audio.music")

        self.sink_name = sink_name
        self.player = self.music_config.get("player", "ffmpeg")

        if self.player != "ffmpeg":
            raise ValueError("Music playback currently supports FFmpeg only.")

        self.music_root = (Path(project_root) / self.music_config["directory"]).resolve()

        self.worker = None
        self.process = None
        self.current_playlist = None

        self.stop_event = threading.Event()
        self.lock = threading.RLock()

    def get_playlist(self, playlist_name):
        directory = (self.music_root / playlist_name).resolve()

        if not directory.is_relative_to(self.music_root):
            raise ValueError("Playlist path must remain inside the music directory.")

        if not directory.is_dir():
            raise FileNotFoundError(f"Music playlist not found: {directory}")

        extensions = set(self.music_config["extensions"]) & self.SUPPORTED_EXTENSIONS

        tracks = sorted(
            (
                path for path in directory.iterdir()
                if path.is_file() and path.suffix.lower() in extensions
            ),
            key=lambda path: path.name.lower()
        )

        if not tracks:
            raise RuntimeError(f"No supported music files found in {directory}")

        return tracks

    def _build_command(self, track):
        return [
            self.player,
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "error",
            "-re",
            "-i",
            str(track),
            "-vn",
            "-f",
            "pulse",
            "-device",
            self.sink_name,
            "Meetinghouse Music",
        ]

    @staticmethod
    def _terminate_process(process):
        if process.poll() is not None:
            return

        try:
            process.terminate()
        except ProcessLookupError:
            return

        try: 
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def _play_track(self, track):
        if self.stop_event.is_set():
            return False

        self.logger.info("Playing music track: %s", track.name)

        process = None

        try:
            with self.lock:
                if self.stop_event.is_set():
                    return False

                process = subprocess.Popen(
                    self._build_command(track),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                
                self.process = process

            while process.poll() is None:
                if self.stop_event.wait(0.25):
                    self._terminate_process(process)
                    return False

            if process.returncode != 0:
                self.logger.error(
                    "Music player exited with status %s: %s",
                    process.returncode,
                    track.name
                )

            return process.returncode == 0
        except OSError:
            self.logger.exception("Unable to start FFmpeg playback.")
            self.stop_event.set()
            return False

        finally:
            if process is not None:
                with self.lock:
                    if self.process is process:
                        self.process = None

    def _play_playlist(self, tracks):
        playlist = list(tracks)

        random.shuffle(playlist)

        self.logger.info(
            "Starting shuffled playlist: %s (%d tracks)",
            self.current_playlist,
            len(playlist),
        )

        for track in playlist:
            if self.stop_event.is_set():
                return

            completed = self._play_track(track)

            if not completed:
                return

        self.logger.info("Playlist completed: %s", self.current_playlist)

    def start_playlist(self, playlist_name):
        tracks = self.get_playlist(playlist_name)

        with self.lock:
            if self.worker and self.worker.is_alive():
                raise RuntimeError("Music playback is already running.")

            self.stop_event.clear()
            self.current_playlist = playlist_name

            self.worker = threading.Thread(
                target=self._play_playlist,
                args=(tracks,),
                name="broadcast-music",
                daemon=True,
            )

            self.worker.start()

        self.logger.info(
            "Started playlist: %s (%s tracks)",
            playlist_name,
            len(tracks)
        )

    def stop(self):
        with self.lock:
            self.stop_event.set()
            process = self.process
            worker = self.worker

        if process is not None:
            self._terminate_process(process)

        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=5)

            if worker.is_alive():
                raise RuntimeError("Music playback worker did not stop.")

        with self.lock:
            self.process = None
            self.worker = None
            self.current_playlist = None

        self.logger.info("Music playback stopped.")

    def is_playing(self):
        with self.lock:
            return (
                self.worker is not None
                and self.worker.is_alive()
            )
