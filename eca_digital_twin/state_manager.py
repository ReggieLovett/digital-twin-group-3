"""State manager for the ECA digital twin.

The :class:`StateManager` holds the current state of the digital twin and
keeps an append-only history of every snapshot so that temporal queries
(e.g. "what was the temperature 10 steps ago?") can be answered without
contacting the physical system.
"""

from __future__ import annotations

import copy
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class StateManager:
    """Manages the live state and historical snapshots of the digital twin.

    Args:
        initial_state: Optional mapping used to seed the initial state.

    Example::

        sm = StateManager({"temperature": 20.0, "pressure": 1.0})
        sm.update({"temperature": 25.0})
        print(sm.current)          # {'temperature': 25.0, 'pressure': 1.0, ...}
        print(len(sm.history))     # 2
    """

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None) -> None:
        self._state: Dict[str, Any] = dict(initial_state or {})
        self._history: List[Dict[str, Any]] = []
        self._snapshot()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def current(self) -> Dict[str, Any]:
        """A shallow copy of the current state dictionary."""
        return dict(self._state)

    @property
    def history(self) -> List[Dict[str, Any]]:
        """All snapshots taken since initialisation (oldest first)."""
        return [dict(snap) for snap in self._history]

    def update(self, changes: Dict[str, Any]) -> None:
        """Merge *changes* into the state and record a new snapshot.

        Args:
            changes: Key-value pairs to add or overwrite in the current state.
        """
        if not changes:
            return
        self._state.update(changes)
        self._snapshot()
        logger.debug("State updated: %s", changes)

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key* in the current state."""
        return self._state.get(key, default)

    def reset(self, new_state: Optional[Dict[str, Any]] = None) -> None:
        """Replace the current state entirely and record a snapshot.

        Args:
            new_state: Replacement state dictionary.  Defaults to ``{}``.
        """
        self._state = dict(new_state or {})
        self._snapshot()
        logger.info("State reset.")

    def snapshot_at(self, index: int) -> Dict[str, Any]:
        """Return the snapshot at position *index* in the history.

        Negative indices are supported (e.g. ``-1`` is the most recent
        snapshot).
        """
        return dict(self._history[index])

    def diff(self, index_a: int = -2, index_b: int = -1) -> Dict[str, Any]:
        """Return keys whose values differ between two history snapshots.

        Args:
            index_a: History index of the earlier snapshot.
            index_b: History index of the later snapshot.

        Returns:
            A dict ``{key: (old_value, new_value)}`` for each changed key.
        """
        snap_a = self._history[index_a]
        snap_b = self._history[index_b]
        all_keys = set(snap_a) | set(snap_b)
        return {
            k: (snap_a.get(k), snap_b.get(k))
            for k in all_keys
            if snap_a.get(k) != snap_b.get(k)
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _snapshot(self) -> None:
        """Append a deep copy of the current state tagged with a timestamp."""
        entry = copy.deepcopy(self._state)
        entry["_timestamp"] = datetime.now(tz=timezone.utc).isoformat()
        self._history.append(entry)
