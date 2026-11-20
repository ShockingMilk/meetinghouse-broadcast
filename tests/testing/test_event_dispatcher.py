from broadcast_controller.testing.event_dispatcher import EventDispatcher
from broadcast_controller.testing.events import HarnessEvent, HarnessEventType


def test_dispatch_calls_matching_handler():
    dispatcher = EventDispatcher()
    received = []

    dispatcher.subscribe(
        HarnessEventType.OBS_CONNECTED,
        received.append,
    )

    event = HarnessEvent(event_type=HarnessEventType.OBS_CONNECTED)

    dispatcher.dispatch(event)

    assert received == [event]


def test_dispatch_calls_global_handler():
    dispatcher = EventDispatcher()
    received = []

    dispatcher.subscribe_all(received.append)

    event = HarnessEvent(event_type=HarnessEventType.HARNESS_STARTED)

    dispatcher.dispatch(event)

    assert received == [event]


def test_unrelated_handler_is_not_called():
    dispatcher = EventDispatcher()
    received = []

    dispatcher.subscribe(
        HarnessEventType.OBS_CONNECTED,
        received.append,
    )

    dispatcher.dispatch(HarnessEvent(event_type=HarnessEventType.HARNESS_STARTED,))

    assert received == []