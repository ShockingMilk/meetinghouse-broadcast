import logging
import socket
import struct

class VISCAController:
    def __init__(self, config):
        self.config = config["camera"]["camera"]
        self.logger = logging.getLogger("broadcast.visca")

        connection = self.config["connection"]
        sequence = self.config["sequence"]

        self.host = connection["host"]
        self.port = connection["port"]
        self.timeout = connection["timeout"]

        self.sequence = sequence["initial_value"]
        self.maximum_sequence = sequence["maximum_value"]

        self.packet_mode = connection["packet_mode"]

        self.socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        self.socket.settimeout(self.timeout)

    def _next_sequence(self):
        current = self.sequence

        self.sequence += 1

        if self.sequence > self.maximum_sequence:
            self.sequence = 1

        return current

    def build_packet(self, payload):
        if self.packet_mode != "visca_over_ip":
            raise ValueError(
                f"Unsupported VISCA packet mode: "
                f"{self.packet_mode}"
            )

        sequence = self._next_sequence()

        # VISCA-over-IP header:
        # Payload type: 0x0100 (command)
        # Payload length: 2-byte big-endian
        # Sequence number: 4-byte big-endian

        header = struct.pack(
            ">HHI",
            0x0100,
            len(payload),
            sequence
        )

        return header + payload

    def recall_preset(self, preset_number):
        if not 0 <= preset_number <= 255:
            raise ValueError(
                "VISCA preset must be between 0 and 255."
            )

        template = self.config["commands"]["recall"]

        command = template.format(
            preset=preset_number
        )

        payload = bytes.fromhex(command)

        packet = self.build_packet(payload)

        sent = self.socket.sendto(
            packet,
            (self.host, self.port)
        )

        self.logger.info(
            "Sent VISCA preset %s to %s:%s (%s bytes).",
            preset_number,
            self.host,
            self.port,
            sent
        )

        # UDP is fire-and-forget. A successful send does not
        # confirm that the camera received or executed the command.

        return sent

    def close(self):
        self.socket.close()
