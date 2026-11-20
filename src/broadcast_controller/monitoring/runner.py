"""Schedule read-only monitoring collectors at their configured intervals."""

import time


class MonitoringRunner:
    def __init__(
        self,
        engine,
        configuration,
        clock=time.monotonic,
        maximum_wait_seconds=1.0,
    ):
        self.engine = engine
        self.configuration = configuration
        self.clock = clock
        self.maximum_wait_seconds = maximum_wait_seconds

    def run(self, stop_event):
        names = self.engine.collector_names
        next_run = {name: self.clock() for name in names}

        while not stop_event.is_set():
            now = self.clock()

            for name in names:
                settings = self.configuration.get_collector_settings(
                    self.engine.session.mode,
                    name,
                )

                if not settings.enabled or now < next_run[name]:
                    continue

                self.engine.run_collector(name)

                next_run[name] = (
                    self.clock() + settings.interval_seconds
                )

            enabled_times = [
                next_run[name]
                for name in names
                if self.configuration.get_collector_settings(
                    self.engine.session.mode,
                    name,
                ).enabled
            ]

            if not enabled_times:
                wait_seconds = self.maximum_wait_seconds
            else:
                wait_seconds = min(
                    self.maximum_wait_seconds,
                    max(0.0, min(enabled_times) - self.clock()),
                )

            stop_event.wait(wait_seconds)
