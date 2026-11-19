import logging
import time

class SceneMonitor:
    def __init__(
        self,
        obs_controller,
        camera_controller,
        audio_service,
        config
    ):
        self.obs = obs_controller
        self.camera = camera_controller
        self.audio = audio_service

        self.config = config
        self.camera_config = config["camera"]["camera"]
        self.obs_config = config["obs"]["obs"]

        self.profiles = config["broadcast_profiles"]["profiles"]

        self.logger = logging.getLogger(
            "broadcast.scene_monitor"
        )

        self.last_scene = None
        self.last_audio_mode = None
        self.last_camera_preset = None

    def _apply_audio(self, scene_name, profile):
        if not self.audio:
            return

        music = profile.get("music", {})
        microphone_enabled = profile.get(
            "microphone",
            False
        )
        music_enabled = music.get("enabled", False)

        if microphone_enabled and music_enabled:
            raise ValueError(
                f"Scene '{scene_name}' enables both microphone and music. This profile is "
                "not supported by the current exclusive audio mode."
            )

        if microphone_enabled:
            audio_signature = ("microphone", None)
        elif music_enabled:
            playlist = music.get("playlist")

            if not playlist:
                raise ValueError(
                    f"Scene '{scene_name}' enables music but has no playlist configured."
                )

            audio_signature = ("music", playlist)
        else:
            audio_signature = ("stopped", None)

        if audio_signature == self.last_audio_mode:
            self.logger.debug(
                "Audio mode unchanged for scene: %s",
                scene_name
            )
            return

        mode, playlist = audio_signature

        if mode == "microphone":
            self.audio.use_microphone()
        elif mode == "music":
            self.audio.use_music(playlist)
        else:
            self.audio.stop()

        self.last_audio_mode = audio_signature

        self.logger.info(
            "Audio mode changed for scene %s: %s",
            scene_name,
            mode if playlist is None else f"{mode} ({playlist})"
        )

    def _apply_camera(self, scene_name, profile):
        if not self.camera:
            return

        if not self.camera_config["enabled"]:
            return

        if "camera_preset" not in profile:
            self.logger.debug(
                "No PTZ preset configured for scene: %s",
                scene_name
            )
            return

        preset = int(profile["camera_preset"])

        if preset == self.last_camera_preset:
            self.logger.debug(
                "PTZ preset unchanged for scene %s: %s",
                scene_name,
                preset
            )
            return

        delay = self.obs_config["scene_monitor"]["transition_settle_seconds"]

        if delay >0:
            time.sleep(delay)

        self.camera.recall_preset(preset)
        self.last_camera_preset = preset

        self.logger.info(
            "Requested camera preset %s for scene %s.",
            preset,
            scene_name
        )

    def process_scene(self, scene_name):
        if not scene_name:
            return

        if scene_name == self.last_scene:
            return

        self.logger.info(
            "OBS program scene changed: %s",
            scene_name
        )

        profile = self.profiles.get(scene_name)

        if profile is None:
            self.logger.warning(
                "No broadcast profile configured for scene: %s",
                scene_name
            )
            self.last_scene = scene_name
            return

        try:
            self._apply_audio(scene_name, profile)
        except Exception:
            self.logger.exception(
                "Unable to apply audio profile for scene: %s",
                scene_name
            )

        try:
            self._apply_camera(scene_name, profile)
        except Exception:
            self.logger.exception(
                "Unable to apply camera profile for scene: %s",
                scene_name
            )
        
        self.last_scene = scene_name

    def initialize(self):
        scene = self.obs.get_current_scene()

        self.process_scene(scene)

    def run(self, stop_event):
        interval = self.obs_config[
            "scene_monitor"
        ]["poll_interval"]

        self.initialize()

        self.logger.info(
            "Scene monitoring started."
        )

        while not stop_event.is_set():
            try:
                scene = self.obs.get_current_scene()

                self.process_scene(scene)

            except Exception:
                self.logger.exception(
                    "Scene monitoring error."
                )

            stop_event.wait(interval)

        self.logger.info(
            "Scene monitoring stopped."
        )
