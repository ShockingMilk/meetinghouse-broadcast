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

if __name__ == "__main__":
    unittest.main()
