from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from .entities import Event


class EventScheduler:
    """Event queue and discrete event simulation scheduler."""

    def __init__(self):
        self._events: List[Event] = []

    def schedule_event(
        self,
        timestamp: datetime,
        event_type: str,
        actor_id: str,
        entity_ids: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
    ) -> Event:
        """Schedules a new discrete event in the simulation."""
        event = Event(
            event_id=event_id or f"evt_{uuid.uuid4().hex[:12]}",
            timestamp=timestamp,
            event_type=event_type,
            actor_id=actor_id,
            entity_ids=entity_ids or {},
            payload=payload or {},
        )
        self._events.append(event)
        return event

    def get_all_events(self) -> List[Event]:
        """Returns all events sorted chronologically by timestamp."""
        return sorted(self._events, key=lambda e: e.timestamp)

    def clear(self) -> None:
        """Clears the event queue."""
        self._events.clear()
