import logging
import signal
import threading
import json
import os

from pathlib import Path

from broadcast_controller.obs.client import OBSController
from broadcast_controller.camera.visca import VISCAController
from broadcast_controller.services.scene_monitor import SceneMonitor
from broadcast_controller.services.zoom import ZoomLauncher
from broadcast_controller.services.audio_service import AudioService
from broadcast_controller.utils.process import (
    is_process_running,
)

class BroadcastLifecycle:

    def __init__(self, config, state_directory):
        self.config = config
        self.state_directory = Path(state_directory)

        self.logger = logging.getLogger(
            "broadcast.lifecycle"
        )

        self.stop_event = threading.Event()

        self.obs = OBSController(config)
        self.camera = None
        self.audio_service = None
        self.monitor = None

        self.virtual_camera_started = False
        self.initial_virtual_camera_state = False

        self.running = False

        self.pid_file = (
            self.state_directory / "controller.pid"
        )

        self.state_file = (
            self.state_directory / "runtime.json"
        )

    def write_state(self):
        data = {
            "controller_pid": os.getpid(),
            "obs_pid": (
                self.obs.process.pid
                if self.obs.process else None
            ),
            "obs_owned": self.obs.owned_process,
            "running": self.running,
        }

        self.state_file.write_text(
            json.dumps(data, indent=4),
            encoding="utf-8"
        )

        self.pid_file.write_text(
            str(os.getpid()),
            encoding="utf-8"
        )

    def cleanup_state(self):
        for path in (self.pid_file, self.state_file):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                self.logger.exception(
                    "Could not remove state file: %s",
                    path
                )

    def request_shutdown(self, signum=None, frame=None):
        self.logger.info(
            "Shutdown requested."
        )

        self.stop_event.set()

    def setup_signals(self):
        signal.signal(
            signal.SIGTERM,
            self.request_shutdown
        )

        signal.signal(
            signal.SIGINT,
            self.request_shutdown
        )

    def start_camera(self):
        camera_config = self.config["camera"]["camera"]

        if not camera_config["enabled"]:
            self.logger.info(
                "PTZ camera integration disabled."
            )
            return

        self.camera = VISCAController(self.config)

        self.logger.info(
            "PTZ controller initialized."
        )

        if self.config["application"]["startup"][
            "recall_initial_preset"
        ]:
            preset = camera_config["initial_preset"]

            self.camera.recall_preset(int(preset))

            self.logger.info(
                "Requested initial camera preset: %s",
                preset
            )

    def start_audio(self):
        audio_config = self.config["audio"]["audio"]

        if not audio_config["enabled"]:
            self.logger.info("Audio integration disabled.")
            return

        self.audio_service = AudioService(self.config)
        self.audio_service.start()

        self.logger.info("Broadcast audio service initialized.")

    def start_obs(self):
        startup_timeout = self.config[
            "application"
        ]["startup"]["startup_timeout"]

        self.obs.ensure_running(
            timeout=startup_timeout
        )

        initial_scene = self.config[
            "obs"
        ]["obs"]["initial_scene"]

        if initial_scene:
            self.obs.set_scene(initial_scene)

        virtual_config = self.config[
            "obs"
        ]["obs"]["virtual_camera"]

        if virtual_config["enabled"]:
            self.initial_virtual_camera_state = (
                self.obs.get_virtual_camera_status()
            )

            if not self.initial_virtual_camera_state:
                self.virtual_camera_started = (
                    self.obs.start_virtual_camera(
                        timeout=virtual_config[
                            "startup_timeout"
                        ]
                    )
                )

    def start_zoom(self):
        launcher = ZoomLauncher(self.config)

        startup = self.config[
            "application"
        ]["startup"]

        if startup["launch_zoom"]:
            launcher.launch()

    def start_monitor(self):
        if not self.camera and not self.audio_service:
            self.logger.info("No camera or audio integrations to monitor.")
            return

        self.monitor = SceneMonitor(
            self.obs,
            self.camera,
            self.audio_service,
            self.config
        )

        # The initial preset may already have been sent by start_camera().
        # Record it to avoid sending it twice if the current OBS scene uses that same preset.
        startup = self.config["application"]["startup"]

        if self.camera and startup["recall_initial_preset"]:
            self.monitor.last_camera_preset = int(self.config["camera"]["camera"]["initial_preset"])

    def run(self):
        self.setup_signals()

        self.logger.info(
            "Starting Meetinghouse Broadcast Controller."
        )

        self.running = True
        self.write_state()

        try:
            self.start_obs()
            self.start_camera()
            self.start_audio()
            self.start_monitor()
            self.start_zoom()

            self.write_state()

            self.logger.info(
                "Meeting system initialized."
            )

            if self.monitor:
                self.monitor.run(self.stop_event)
            else:
                self.stop_event.wait()

        except Exception:
            self.logger.exception(
                "Startup/runtime failure."
            )
            raise

        finally:
            self.shutdown()

    def shutdown(self):
        self.logger.info(
            "Beginning graceful shutdown."
        )

        self.stop_event.set()

        shutdown_config = self.config[
            "application"
        ]["shutdown"]

        if self.audio_service:
            try:
                self.audio_service.shutdown()
            except Exception:
                self.logger.exception("Unable to shut down audio service.")

        if (
            shutdown_config["stop_virtual_camera"]
            and self.virtual_camera_started
            and self.obs.client
        ):
            try:
                self.obs.stop_virtual_camera()
            except Exception:
                self.logger.exception("Unable to stop OBS virtual camera.")

        if self.camera:
            try:
                self.camera.close()
            except Exception:
                self.logger.exception("Unable to close PTZ controller.")

        if shutdown_config["close_owned_obs"]:
            timeout = self.config[
                "application"
            ]["startup"]["shutdown_timeout"]

            try:
                self.obs.close(timeout=timeout)
            except Exception:
                self.logger.exception("Unable to close owned OBS process.")

        self.running = False
        self.cleanup_state()

        self.logger.info(
            "Broadcast controller stopped."
        )
