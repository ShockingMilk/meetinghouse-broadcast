import unittest

from broadcast_controller.camera.visca import VISCAController

class VISCATests(unittest.TestCase):

    def setUp(self):
        self.config = {
            "camera": {
                "camera": {
                    "connection": {
                        "host": "192.168.1.200",
                        "port": 52381,
                        "timeout": 1.0,
                        "transport": "udp",
                        "packet_mode": "visca_over_ip",
                    },
                    "sequence": {
                        "initial_value": 1,
                        "maximum_value": 4294967295,
                    },
                    "commands": {
                        "recall": "8101043F02{preset:02X}FF"
                    }
                }
            }
        }

        self.controller = VISCAController(self.config)

    def tearDown(self):
        self.controller.close()

    def test_packet_header(self):
        payload = bytes.fromhex(
            "8101043F0201FF"
        )

        packet = self.controller.build_packet(payload)

        self.assertEqual(
            packet[:8].hex(),
            "0100000700000001"
        )

        self.assertEqual(packet[8:], payload)

    def test_sequence_increments(self):
        first = self.controller.build_packet(
            bytes.fromhex("8101043F0201FF")
        )

        second = self.controller.build_packet(
            bytes.fromhex("8101043F0202FF")
        )

        self.assertEqual(
            first[4:8],
            bytes.fromhex("00000001")
        )

        self.assertEqual(
            second[4:8],
            bytes.fromhex("00000002")
        )

    def test_invalid_preset(self):
        with self.assertRaises(ValueError):
            self.controller.recall_preset(300)

if __name__ == "__main__":
    unittest.main()
