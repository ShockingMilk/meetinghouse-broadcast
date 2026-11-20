import unittest
import os

from unittest.mock import patch

from broadcast_controller.config import load_config

class ConfigTests(unittest.TestCase):

    def test_configuration_loads(self):
        config = load_config()

        self.assertIn("application", config)
        self.assertIn("obs", config)
        self.assertIn("camera", config)
        self.assertIn("zoom", config)

    def test_monitoring_configuration_loads(self):
        config = load_config()

        self.assertIn("monitoring", config)

        monitoring = config["monitoring"]["monitoring"]

        self.assertEqual(monitoring["default_mode"], "passive")

        self.assertIn("passive", monitoring["modes"])

    def test_camera_has_connection_settings(self):
        config = load_config()

        camera = config["camera"]["camera"]

        self.assertIn("host", camera["connection"])
        self.assertIn("port", camera["connection"])

    def test_environment_variables_are_loaded(self):
        environment = {
            "OBS_WS_HOST": "10.0.0.10",
            "OBS_WS_PORT": "4456",
            "OBS_WS_PASSWORD": "test-password",
            "OBS_INPUT_NAME": "Test Camera",
            "ZOOM_MEETING_URL": "https://zoom.us/test",
            "ZOOM_MEETING_PASSCODE": "test-passcode",
            "CAMERA_CONNECTION_HOST": "10.0.0.20",
            "CAMERA_CONNECTION_PORT": "52381",
        }

        with patch.dict(os.environ, environment):
            config = load_config()

            # OBS WebSocket
            self.assertEqual(
                config["obs"]["obs"]["websocket"]["host"],
                "10.0.0.10",
            )
            self.assertEqual(
                config["obs"]["obs"]["websocket"]["port"],
                4456,
            )
            self.assertEqual(
                config["obs"]["obs"]["websocket"]["password"],
                "test-password",
            )

            # OBS Camera Source
            self.assertEqual(
                config["camera"]["camera"]["monitoring"]["obs_input_name"],
                "Test Camera",
            )

            # Zoom
            self.assertEqual(
                config["zoom"]["zoom"]["meeting_url"],
                "https://zoom.us/test",
            )
            self.assertEqual(
                os.getenv("ZOOM_MEETING_PASSCODE"),
                "test-passcode",
            )

            # PTZ Camera
            self.assertEqual(
                config["camera"]["camera"]["connection"]["host"],
                "10.0.0.20",
            )
            self.assertEqual(
                config["camera"]["camera"]["connection"]["port"],
                52381,
            )


    def test_invalid_environment_port_raises_error(self):
        with patch.dict(os.environ, {"OBS_WS_PORT": "not-a-port"}):
            with self.assertRaisesRegex(ValueError, "OBS_WS_PORT"):
                load_config()

if __name__ == "__main__":
    unittest.main()
