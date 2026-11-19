import unittest
from unittest.mock import Mock

from broadcast_controller.services.scene_monitor import (
    SceneMonitor
)

class FakeOBS:

    def get_current_scene(self):
        return "00 - Opening"

class FakeCamera:

    def __init__(self):
        self.presets = []

    def recall_preset(self, preset):
        self.presets.append(preset)

class SceneMappingTests(unittest.TestCase):

    def setUp(self):
        self.config = {
            "camera": {
                "camera": {
                    "enabled": True,
                    "initial_preset": 0,
                }
            },
            "obs": {
                "obs": {
                    "scene_monitor": {
                        "transition_settle_seconds": 0,
                        "poll_interval": 0.1,
                    }
                }
            },
            "broadcast_profiles": {
                "profiles": {
                    "00 - Default": {
                        "camera": False,
                        "camera_preset": 0,
                        "microphone": False,
                        "music": {
                            "playlist": "prelude_postlude",
                            "enabled": True,
                        },
                    },
                    "01 - Speaker": {
                        "camera": True,
                        "camera_preset": 1,
                        "microphone": True,
                        "music": {"enabled": False}
                    },
                    "02 - Chorister": {
                        "camera": True,
                        "camera_preset": 2,
                        "microphone": True,
                        "music": {"enabled": False}
                    },
                    "03 - Choir": {
                        "camera": True,
                        "camera_preset": 3,
                        "microphone": True,
                        "music": {"enabled": False}
                    },
                    "04 - Sacrament": {
                        "camera": False,
                        "camera_preset": 0,
                        "microphone": False,
                        "music": {
                            "playlist": "sacrament",
                            "enabled": True,
                        }
                    }
                }
            }
        }

        self.obs = FakeOBS()
        self.camera = FakeCamera()
        self.audio = Mock()

        self.monitor = SceneMonitor(
            self.obs,
            self.camera,
            self.audio,
            self.config
        )

    def test_scene_selects_preset(self):
        self.monitor.process_scene("01 - Speaker")

        self.assertEqual(
            self.camera.presets,
            [1]
        )

    def test_repeated_scene_is_ignored(self):
        self.monitor.process_scene("01 - Speaker")
        self.monitor.process_scene("01 - Speaker")

        self.assertEqual(
            self.camera.presets,
            [1]
        )

        self.audio.use_microphone.assert_called_once()

    def test_unmapped_scene_does_not_move_camera(self):
        self.monitor.process_scene("Unmapped Scene")

        self.assertEqual(
            self.camera.presets,
            []
        )

        self.audio.use_microphone.assert_not_called()
        self.audio.use_music.assert_not_called()

    def test_different_scenes_select_different_presets(self):
        self.monitor.process_scene("01 - Speaker")
        self.monitor.process_scene("02 - Chorister")

        self.assertEqual(
            self.camera.presets,
            [1, 2]
        )

    def test_default_and_sacrament_share_preset_zero(self):
        self.monitor.process_scene("00 - Default")
        self.monitor.process_scene("04 - Sacrament")

        self.assertEqual(
            self.camera.presets,
            [0]
        )

        self.audio.use_music.assert_any_call("prelude_postlude")
        self.audio.use_music.assert_any_call("sacrament")

if __name__ == "__main__":
    unittest.main()
