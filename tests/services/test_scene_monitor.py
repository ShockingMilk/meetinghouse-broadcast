from unittest.mock import Mock

import pytest

from broadcast_controller.services.scene_monitor import SceneMonitor

@pytest.fixture
def config():
    return {
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
                    "music": {"enabled": False},
                },
                "02 - Chorister": {
                    "camera": True,
                    "camera_preset": 2,
                    "microphone": True,
                    "music": {"enabled": False},
                },
                "03 - Choir": {
                    "camera": True,
                    "camera_preset": 3,
                    "microphone": True,
                    "music":{"enabled": False},
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

@pytest.fixture
def monitor(config):
    obs = Mock()
    camera = Mock()
    audio= Mock()

    return SceneMonitor(obs, camera, audio, config), obs, camera, audio

def test_default_scene_starts_prelude_music(monitor):
    scene_monitor, obs, camera, audio = monitor

    scene_monitor.process_scene("00 - Default")

    audio.use_music.assert_called_once_with("prelude_postlude")
    camera.recall_preset.assert_called_once_with(0)

def test_speaker_scene_uses_microphone(monitor):
    scene_monitor, obs, camera, audio = monitor

    scene_monitor.process_scene("01 - Speaker")

    audio.use_microphone.assert_called_once()
    camera.recall_preset.assert_called_once_with(1)

def test_chorister_scene_uses_microphone(monitor):
    scene_monitor, obs, camera, audio = monitor

    scene_monitor.process_scene("02 - Chorister")

    audio.use_microphone.assert_called_once()
    camera.recall_preset.assert_called_once_with(2)

def test_choir_scene_uses_microphone(monitor):
    scene_monitor, obs, camera, audio = monitor

    scene_monitor.process_scene("03 - Choir")

    audio.use_microphone.assert_called_once()
    camera.recall_preset.assert_called_once_with(3)

def test_sacrament_scene_uses_music_and_default_preset(monitor):
    scene_monitor, obs, camera, audio = monitor

    scene_monitor.process_scene("04 - Sacrament")

    audio.use_music.assert_called_once_with("sacrament")
    camera.recall_preset.assert_called_once_with(0)

def test_same_scene_does_not_repeat_actions(monitor):
    scene_monitor, obs, camera, audio = monitor

    scene_monitor.process_scene("00 - Default")
    scene_monitor.process_scene("00 - Default")

    audio.use_music.assert_called_once_with("prelude_postlude")
    camera.recall_preset.assert_called_once_with(0)

def test_switching_to_sacrament_does_not_recall_same_camera_preset(monitor):
    scene_monitor, obs, camera, audio = monitor

    scene_monitor.process_scene("00 - Default")
    scene_monitor.process_scene("04 - Sacrament")

    assert camera.recall_preset.call_count == 1

    audio.use_music.assert_any_call("prelude_postlude")
    audio.use_music.assert_any_call("sacrament")

def test_switching_between_microphone_scenes_does_not_restart_audio(monitor):
    scene_monitor, obs, camera, audio = monitor

    scene_monitor.process_scene("01 - Speaker")
    scene_monitor.process_scene("02 - Chorister")
    scene_monitor.process_scene("03 - Choir")

    audio.use_microphone.assert_called_once()

def test_unknown_scene_does_not_change_audio_or_camera(monitor):
    scene_monitor, obs, camera, audio = monitor

    scene_monitor.process_scene("Unknown Scene")

    audio.use_microphone.assert_not_called()
    audio.use_music.assert_not_called()
    audio.stop.assert_not_called()

    camera.recall_preset.assert_not_called()

def test_missing_scene_name_is_ignored(monitor):
    scene_monitor, obs, camera, audio = monitor

    scene_monitor.process_scene("")

    audio.use_microphone.assert_not_called()
    audio.use_music.assert_not_called()
    camera.recall_preset.assert_not_called()

def test_audio_failure_does_not_prevent_camera_change(monitor):
    scene_monitor, obs, camera, audio = monitor

    audio.use_microphone.side_effect = RuntimeError("Audio failure")

    scene_monitor.process_scene("01 - Speaker")

    camera.recall_preset.assert_called_once_with(1)
