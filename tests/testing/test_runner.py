from broadcast_controller.monitoring.runner import MonitoringRunner


class FakeStopEvent:
    def __init__(self, stop_after_waits=1):
        self.waits = []
        self.stop_after_waits = stop_after_waits
        self.stopped = False

    def is_set(self):
        return self.stopped

    def wait(self, seconds):
        self.waits.append(seconds)

        if len(self.waits) >= self.stop_after_waits:
            self.stopped = True


class FakeEngine:
    collector_names = ("network", "system")

    def __init__(self):
        self.calls = []
        self.session = type("Session", (), {"mode": "passive"})()

    def run_collector(self, name):
        self.calls.append(name)


class FakeSettings:
    enabled = True

    def __init__(self, interval):
        self.interval_seconds = interval


class FakeConfiguration:
    def get_collector_settings(self, mode, name):
        intervals = {
            "network": 5,
            "system": 15,
        }
        return FakeSettings(intervals[name])


def test_runner_runs_due_collectors():
    engine = FakeEngine()
    stop_event = FakeStopEvent()

    runner = MonitoringRunner(
        engine,
        FakeConfiguration(),
        clock=lambda: 100.0,
    )

    runner.run(stop_event)

    assert engine.calls == ["network", "system"]


def test_runner_wait_is_bounded():
    engine = FakeEngine()
    stop_event = FakeStopEvent()

    runner = MonitoringRunner(
        engine,
        FakeConfiguration(),
        clock=lambda: 100.0,
        maximum_wait_seconds=1.0,
    )

    runner.run(stop_event)

    assert stop_event.waits
    assert all(wait <= 1.0 for wait in stop_event.waits)
