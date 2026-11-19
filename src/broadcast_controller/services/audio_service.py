import logging

from broadcast_controller.audio.router import AudioRouter
from broadcast_controller.audio.music_manager import MusicManager
from broadcast_controller.config import get_project_root

class AudioService:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("broadcast.audio.service")

        self.audio_config = config["audio"]["audio"]
        self.enabled = self.audio_config["enabled"]
        self.behavior = self.audio_config["behavior"]

        self.router = AudioRouter(config)

        self.music = MusicManager(
            config,
            self.router.sink_name,
            get_project_root()
        )

        self.active_mode = "stopped"

    def start(self):
        if not self.enabled:
            self.logger.info("Audio integration is disabled.")
            return

        self.router.create_virtual_device()

        self.logger.info("Broadcast audio service initialized.")

    def use_microphone(self):
        if not self.enabled:
            raise RuntimeError("Audio integration is disabled.")

        if self.behavior["stop_music_before_microphone"]:
            self.music.stop()

        self.router.start_microphone()

        self.active_mode = "microphone"

        self.logger.info("Audio mode changed to microphone.")

    def use_music(self, playlist_name):
        if not self.enabled:
            raise RuntimeError("Audio integration is disabled.")
        
        self.router.create_virtual_device()

        if self.behavior["stop_microphone_before_music"]:
            self.router.stop_microphone()
        
        # Always stop an existing playlist before starting another.
        self.music.stop()

        self.music.start_playlist(playlist_name)

        self.active_mode = "music"

        self.logger.info(
            "Audio mode changed to music: %s",
            playlist_name,
        )

    def stop(self):
        self.music.stop()
        self.router.stop_microphone()

        self.active_mode = "stopped"

        self.logger.info("Audio service stopped.")

    def get_status(self):
        return {
            "enabled": self.enabled,
            "mode": self.active_mode,
            "router": self.router.get_status(),
            "music_playing": self.music.is_playing(),
            "playlist": self.music.current_playlist,
        }

    def shutdown(self):
        try: 
            self.stop()
        finally:
            self.router.cleanup()

        self.logger.info("Broadcast audio service shut down.")
