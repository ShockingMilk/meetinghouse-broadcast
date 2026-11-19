import logging
import subprocess

class AudioRouter:
    def __init__(self, config):
        self.config = config["audio"]["audio"]
        self.logger = logging.getLogger("broadcast.audio.router")

        virtual = self.config["virtual_device"]

        self.sink_name = virtual["sink_name"]
        self.monitor_name = f"{self.sink_name}.monitor"

        self.microphone_input_name = virtual.get(
            "microphone_source_name",
            f"{self.sink_name}_mic",
        )

        self.microphone_description = virtual.get(
            "microphone_description",
            "Meetinghouse Broadcast Microphone",
        )

        self.sink_module = None
        self.remap_module = None
        self.microphone_module = None
        
        self.owns_sink = False
        self.owns_remap_source = False

        self.microphone_source = None

    def _run(self, arguments, check=True):
        return subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            check=check,
        )

    def _output(self, arguments):
        result = self._run(arguments)
        return result.stdout.strip()

    def _list_devices(self, device_type):
        output = self._output([
            "pactl",
            "list",
            "short",
            device_type,
        ])

        devices = set()

        for line in output.splitlines():
            fields = line.split()

            if len(fields) >= 2:
                devices.add(fields[1])

        return devices

    def _sink_exists(self):
        return self.sink_name in self._list_devices("sinks")

    def _source_exists(self, source_name):
        return source_name in self._list_devices("sources")

    def _get_default_source(self):
        return self._output([
            "pactl",
            "get-default-source",
        ])

    def get_microphone_source(self):
        microphone = self.config["microphone"]

        preferred = microphone.get("preferred_source", "")
        fallback = microphone.get("fallback_source", "")

        if preferred and self._source_exists(preferred):
            return preferred

        if fallback and self._source_exists(fallback):
            self.logger.warning(
                "Preferred microphone unavailable; using fallback: %s",
                fallback
            )
            return fallback

        default_source = self._get_default_source()

        if (
            default_source
            and not default_source.endswith(".monitor")
            and self._source_exists(default_source)
        ):
            return default_source

        raise RuntimeError(
            "No usable physical microphone source was found."
        )

    def create_virtual_device(self):
        if not self._sink_exists():
            virtual = self.config["virtual_device"]

            description = virtual["description"].replace(" ", "_")
            properties = (
                f"device.description={description}"
            )

            module_id = self._output([
                "pactl",
                "load-module",
                "module-null-sink",
                f"sink_name={self.sink_name}",
                f"sink_properties={properties}",
                f"rate={virtual['sample_rate']}",
                f"channels={virtual['channels']}",
            ])

            self.sink_module = module_id
            self.owns_sink = True

            self.logger.info(
                "Created virtual audio sink: %s",
                self.sink_name,
            )

        if not self._source_exists(self.monitor_name):
            raise RuntimeError(
                "Virtual sink exists, but its monitor source is unavailable."
            )

        self._create_remapped_microphone()
    
    def _create_remapped_microphone(self):
        if self._source_exists(self.microphone_input_name):
            self.logger.info(
                "Virtual microphone already exists: %s",
                self.microphone_input_name,
            )
            return

        description = self.microphone_description.replace(" ", "_")
        properties = (
            f"device.description={description}"
        )

        module_id = self._output([
            "pactl",
            "load-module",
            "module-remap-source",
            f"master={self.monitor_name}",
            f"source_name={self.microphone_input_name}",
            f"source_properties={properties}",
        ])

        self.remap_module = module_id
        self.owns_remap_source = True

        if not self._source_exists(self.microphone_input_name):
            raise RuntimeError("Remapped microphone was created, but its source is unavailable.")

        self.logger.info(
            "created virtual microphone: %s",
            self.microphone_input_name,
        )

    def start_microphone(self):
        self.create_virtual_device()

        if self.microphone_module is not None:
            self.logger.info(
                "Microphone routing is already active."
            )
            return

        source = self.get_microphone_source()

        latency = self.config["microphone"]["latency_msec"]

        module_id = self._output([
            "pactl",
            "load-module",
            "module-loopback",
            f"source={source}",
            f"sink={self.sink_name}",
            f"latency_msec={latency}",
        ])

        self.microphone_module = module_id
        self.microphone_source = source

        self.logger.info(
            "Microphone routed to broadcast device: %s",
            source
        )

    def stop_microphone(self):
        if self.microphone_module is None:
            return

        module_id = self.microphone_module

        self._run([
            "pactl",
            "unload-module",
            module_id,
        ])

        self.microphone_module = None
        self.microphone_source = None

        self.logger.info("Microphone routing stopped.")

    def get_status(self):
        return {
            "sink": self.sink_name,
            "monitor": self.monitor_name,
            "microphone_input": self.microphone_input_name,
            "sink_exists": self._sink_exists(),
            "microphone_input_exists": self._source_exists(self.microphone_input_name),
            "microphone_active": (
                self.microphone_module is not None
            ),
            "microphone_source": self.microphone_source,
        }

    def cleanup(self):
        try:
            self.stop_microphone()
        except Exception:
            self.logger.exception(
                "Unable to stop microphone routing."
            )

        if self.owns_remap_source and self.remap_module is not None:
            try:
                self._run([
                    "pactl",
                    "unload-module",
                    self.remap_module,
                ])
                self.logger.info("Virtual microphone removed.")
            except Exception:
                self.logger.exception("Unable to remove virtual microphone.")

        self.remap_module = None
        self.owns_remap_source = False

        if (
            self.owns_sink
            and self.sink_module is not None
            and self.config["behavior"]["cleanup_virtual_device_on_shutdown"]
        ):
            try:
                self._run([
                    "pactl",
                    "unload-module",
                    self.sink_module,
                ])

                self.logger.info("Virtual audio device removed.")
            except Exception:
                self.logger.exception("Unable to remove virtual audio device.")

        self.sink_module = None
        self.owns_sink = False
