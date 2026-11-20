import unittest

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

    def test_environment_variables_are_loaded(monkeypatch):
        monkeypatch.setenv("OBS_WS_HOST", "10.0.0.10")
        monkeypatch.setenv("OBS_WS_PORT", "4456")
        monkeypatch.setenv("OBS_WS_PASSWORD", "test-password")

        monkeypatch.setenv("OBS_INPUT_NAME", "Test Camera")
        monkeypatch.setenv("ZOOM_MEETING_URL", "https://zoom.us/test")

        monkeypatch.setenv("CAMERA_CONNECTION_HOST", "10.0.0.20")
        monkeypatch.setenv("CAMERA_CONNECTION_PORT", "52381")

        config = load_config()

        assert config["obs"]["obs"]["websocket"]["host"] == "10.0.0.10"
        assert config["obs"]["obs"]["websocket"]["port"] == 4456
        assert config["obs"]["obs"]["websocket"]["password"] == "test-password"

        assert config["camera"]["camera"]["monitoring"]["obs_input_name"] == "Test Camera"

        assert config["zoom"]["zoom"]["meeting_url"] == "https://zoom.us/test"

        assert config["camera"]["camera"]["connection"]["host"] == "10.0.0.20"
        assert config["camera"]["camera"]["connection"]["port"] == 52381


    def test_invalid_environment_port_raises_error(monkeypatch):
        monkeypatch.setenv("OBS_WS_PORT", "not-a-port")

        try:
            load_config()
            assert False, "Expected invalid port to raise ValueError"
        except ValueError as error:
            assert "OBS_WS_PORT" in str(error)

if __name__ == "__main__":
    unittest.main()
