import logging
import shutil
import subprocess
import time

import obsws_python as obs

class OBSController:
    def __init__(self, config):
        self.config = config["obs"]["obs"]
        self.logger = logging.getLogger("broadcast.obs")

        self.client = None
        self.process = None
        self.owned_process = False

    def _connection_settings(self):
        settings = self.config["websocket"]

        return {
            "host": settings["host"],
            "port": settings["port"],
            "password": settings["password"],
            "timeout": settings["timeout"],
        }

    def connect(self):
        self.client = obs.ReqClient(
            **self._connection_settings()
        )

        self.client.get_version()

        self.logger.info("Connected to OBS WebSocket.")

        return True

    def is_available(self):
        try:
            self.connect()
            return True
        except Exception:
            return False

    def launch(self):
        executable = self.config["executable"]

        if not shutil.which(executable):
            raise FileNotFoundError(
                f"OBS executable not found: {executable}"
            )

        arguments = [executable]

        if self.config.get("profile"):
            arguments.extend([
                "--profile",
                self.config["profile"]
            ])

        if self.config.get("scene_collection"):
            arguments.extend([
                "--collection",
                self.config["scene_collection"]
            ])

        if self.config.get("initial_scene"):
            arguments.extend([
                "--scene",
                self.config["initial_scene"]
            ])

        self.logger.info("Launching OBS: %s", arguments)

        self.process = subprocess.Popen(
            arguments,
            start_new_session=True,
        )

        self.owned_process = True

    def ensure_running(self, timeout=45):
        if self.is_available():
            self.logger.info(
                "OBS already running; using existing instance."
            )
            return

        self.launch()

        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(
                    "OBS exited before WebSocket became available."
                )

            try:
                self.connect()
                return
            except Exception:
                time.sleep(1)

        raise TimeoutError(
            "OBS WebSocket did not become available."
        )

    def set_scene(self, scene_name):
        self.client.set_current_program_scene(scene_name)

        self.logger.info(
            "Set OBS program scene: %s",
            scene_name
        )

    def get_current_scene(self):
        response = self.client.send(
            "GetCurrentProgramScene",
            raw=True
        )

        return (
            response.get("currentProgramSceneName")
            or response.get("sceneName")
        )

    def get_virtual_camera_status(self):
        response = self.client.send(
            "GetVirtualCamStatus",
            raw=True
        )

        return response.get("outputActive", False)

    def start_virtual_camera(self, timeout=20):
        if self.get_virtual_camera_status():
            self.logger.info(
                "OBS Virtual Camera already active."
            )
            return False

        self.client.send("StartVirtualCam")

        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self.get_virtual_camera_status():
                self.logger.info(
                    "OBS Virtual Camera started."
                )
                return True

            time.sleep(1)

        raise TimeoutError(
            "OBS Virtual Camera failed to start."
        )

    def stop_virtual_camera(self):
        if not self.client:
            return

        try:
            if self.get_virtual_camera_status():
                self.client.send("StopVirtualCam")

                self.logger.info(
                    "OBS Virtual Camera stopped."
                )
        except Exception:
            self.logger.exception(
                "Unable to stop OBS Virtual Camera."
            )

    def close(self, timeout=15):
        if not self.owned_process or not self.process:
            self.logger.info(
                "OBS was not started by this application; "
                "leaving it open."
            )
            return

        self.logger.info("Closing owned OBS process.")

        self.process.terminate()

        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.logger.warning(
                "OBS did not exit gracefully; forcing termination."
            )
            self.process.kill()
            self.process.wait()

        self.logger.info("OBS process closed.")
