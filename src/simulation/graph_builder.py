from datetime import datetime
from typing import Dict, List, Tuple
from .entities import Relationship


class GraphBuilder:
    """Tracks and builds entity relationships (User-Device, User-Address, User-Payment)."""

    def __init__(self):
        # Key: (user_id, entity_type, entity_id) -> [first_seen, last_seen]
        self._edges: Dict[Tuple[str, str, str], List[datetime]] = {}

    def record_interaction(
        self, user_id: str, entity_type: str, entity_id: str, timestamp: datetime
    ) -> None:
        """Records or updates an edge between a user and an associated entity."""
        if not user_id or not entity_id or not entity_type:
            return

        key = (user_id, entity_type, entity_id)
        if key not in self._edges:
            self._edges[key] = [timestamp, timestamp]
        else:
            if timestamp < self._edges[key][0]:
                self._edges[key][0] = timestamp
            if timestamp > self._edges[key][1]:
                self._edges[key][1] = timestamp

    def get_relationships(self) -> List[Relationship]:
        """Returns all recorded relationships as a list of Relationship objects."""
        relationships = []
        for (user_id, entity_type, entity_id), (first_seen, last_seen) in self._edges.items():
            relationships.append(
                Relationship(
                    user_id=user_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    first_seen=first_seen,
                    last_seen=last_seen,
                )
            )
        return relationships
