from collections import defaultdict
from typing import Callable

from broadcast_controller.testing.events import HarnessEvent, HarnessEventType


EventHandler = Callable[[HarnessEvent], None]


class EventDispatcher:
    """Dispatch harness events to registered handlers."""

    def __init__(self):
        self._handlers = defaultdict(list)
        self._all_handlers = []

    def subscribe(
        self,
        event_type: HarnessEventType,
        handler: EventHandler,
    ) -> None:
        if not isinstance(event_type, HarnessEventType):
            raise TypeError("Invalid event type.")

        if not callable(handler):
            raise TypeError("Event handler must be callable.")

        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        if not callable(handler):
            raise TypeError("Event handler must be callable.")

        self._all_handlers.append(handler)

    def dispatch(self, event: HarnessEvent) -> None:
        if not isinstance(event, HarnessEvent):
            raise TypeError("Only HarnessEvent objects can be dispatched.")

        for handler in tuple(self._all_handlers):
            handler(event)

        for handler in tuple(self._handlers[event.event_type]):
            handler(event)