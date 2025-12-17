"""Event system for market data notifications."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast

logger = logging.getLogger(__name__)


@dataclass
class BaseEvent:
    """Base class for all market data events."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CandleCloseEvent(BaseEvent):
    """Event triggered when a candle closes."""

    symbol: str = ""
    interval: str = ""
    candle: Dict[str, Any] = field(default_factory=dict)  # Raw candle data
    close_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EventType(Enum):
    """Types of market data events."""

    CANDLE_CLOSE = auto()
    # Add other event types as needed


# Define a custom Callable type that mypy understands for decorator attributes
_EventHandlerCallable = TypeVar("_EventHandlerCallable", bound=Callable[..., Any])


def event_handler(
    event_type: EventType, interval: Optional[str] = None
) -> Callable[[_EventHandlerCallable], _EventHandlerCallable]:
    """
    Decorator for event handler methods.

    Args:
        event_type: The type of event to handle.
        interval: Optional interval filter for the event.
    """

    def decorator(func: _EventHandlerCallable) -> _EventHandlerCallable:
        # Cast func to Any before assigning attributes mypy doesn't expect on a raw Callable
        # This is a common pattern for decorators that add metadata
        wrapped_func = cast(Any, func)
        wrapped_func._is_event_handler = True
        wrapped_func._event_type = event_type
        wrapped_func._interval = interval
        return func

    return decorator


class EventManager:
    """Manages event handlers and dispatching."""

    def __init__(self) -> None:
        """Initialize the event manager."""
        self._event_handlers: Dict[
            EventType, Dict[Optional[str], List[Callable[[BaseEvent], Any]]]
        ] = {EventType.CANDLE_CLOSE: {}}

    def register_handler(
        self,
        event_type: EventType,
        handler: Callable[[BaseEvent], Any],
        interval: Optional[str] = None,
    ) -> None:
        """Register an event handler for a specific event type and optional interval.

        Args:
            event_type: The type of event to handle
            handler: The handler function to call
            interval: Optional interval filter (e.g., '1h', '4h')
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = {}

        if interval not in self._event_handlers[event_type]:
            self._event_handlers[event_type][interval] = []

        self._event_handlers[event_type][interval].append(handler)
        logger.debug(
            f"Registered {event_type.name} handler for interval {interval}: {handler.__name__}"
        )

    async def trigger_event(
        self, event: BaseEvent, event_type: EventType, interval: Optional[str] = None
    ) -> None:
        """Trigger all handlers for a specific event type and optional interval.

        Args:
            event: The event object to pass to handlers
            event_type: The type of event being triggered
            interval: Optional interval filter
        """
        if event_type not in self._event_handlers:
            return

        # Get handlers for this specific interval and global handlers (None interval)
        handlers = []
        if interval in self._event_handlers[event_type]:
            handlers.extend(self._event_handlers[event_type][interval])
        if None in self._event_handlers[event_type]:
            handlers.extend(self._event_handlers[event_type][None])

        # Execute all handlers concurrently
        if handlers:
            await asyncio.gather(
                *[self._safe_execute_handler(h, event) for h in handlers],
                return_exceptions=True,
            )

    async def _safe_execute_handler(
        self, handler: Callable[[BaseEvent], Any], event: BaseEvent
    ) -> None:
        """Execute a single event handler with error handling.

        Args:
            handler: The handler function to execute
            event: The event object to pass to the handler
        """
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                # Handle synchronous handlers
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, handler, event)
        except Exception as e:
            logger.error(f"Error in {handler.__name__}: {e}", exc_info=True)
