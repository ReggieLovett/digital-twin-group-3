"""Core digital twin orchestrator.

The :class:`DigitalTwin` is the top-level component that ties together:

* A :class:`~state_manager.StateManager` – maintains the live state of
  the twin and its history.
* An :class:`~eca_model.ECAEngine` – evaluates ECA rules against incoming
  events.
* An optional :class:`~simulator.Simulator` – drives the twin with
  synthetic data when the physical system is unavailable.

Typical usage
-------------
::

    from eca_digital_twin import DigitalTwin, Rule, Condition, Action, Event

    twin = DigitalTwin(name="my_eca", initial_state={"temperature": 20.0})

    twin.add_rule(Rule(
        event_name="temperature_changed",
        condition=Condition(
            lambda e: e.payload.get("value", 0) > 80,
            description="temperature > 80",
        ),
        action=Action(
            lambda e, s: s.update({"alert": "overheating"}),
            name="raise_overheating_alert",
        ),
        name="overheating_rule",
    ))

    twin.ingest(Event("temperature_changed", {"value": 95}))
    print(twin.state)  # {'temperature': 20.0, 'alert': 'overheating', ...}
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .eca_model import ECAEngine, Event, Rule
from .simulator import Simulator
from .state_manager import StateManager

logger = logging.getLogger(__name__)


class DigitalTwin:
    """ECA digital twin that synchronises with, or simulates, a physical system.

    Args:
        name: Human-readable identifier for this twin instance.
        initial_state: Optional seed state for the :class:`StateManager`.
        simulator: Optional :class:`Simulator` instance.  If *None*, one is
            created with default settings (useful for quick demos).
    """

    def __init__(
        self,
        name: str = "eca_twin",
        initial_state: Optional[Dict[str, Any]] = None,
        simulator: Optional[Simulator] = None,
    ) -> None:
        self.name = name
        self._state_manager = StateManager(initial_state)
        self._engine = ECAEngine()
        self._simulator = simulator if simulator is not None else Simulator()
        logger.info("DigitalTwin '%s' initialised.", self.name)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> Dict[str, Any]:
        """Current state of the digital twin."""
        return self._state_manager.current

    @property
    def history(self) -> List[Dict[str, Any]]:
        """Full state history (oldest first)."""
        return self._state_manager.history

    @property
    def rules(self) -> List[Rule]:
        """Rules currently registered in the ECA engine."""
        return self._engine.rules

    @property
    def fired_log(self) -> List[Dict[str, Any]]:
        """Log of every rule that has been fired since twin creation."""
        return self._engine.fired_log

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: Rule) -> None:
        """Register an ECA rule with the twin's engine.

        Args:
            rule: The :class:`~eca_model.Rule` to add.
        """
        self._engine.add_rule(rule)

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name.

        Args:
            name: The ``name`` attribute of the rule to remove.

        Returns:
            ``True`` if the rule was found and removed, ``False`` otherwise.
        """
        return self._engine.remove_rule(name)

    # ------------------------------------------------------------------
    # Event ingestion
    # ------------------------------------------------------------------

    def ingest(self, event: Event) -> List[Rule]:
        """Feed an external event into the twin.

        The state snapshot held by the :class:`StateManager` is passed as the
        mutable ``state`` argument to each action so that actions can update
        the twin's state directly.

        Args:
            event: The :class:`~eca_model.Event` to process.

        Returns:
            The list of rules whose actions were fired.
        """
        mutable_state = self._state_manager.current
        fired = self._engine.process(event, mutable_state)
        # Persist any state changes made by actions
        self._state_manager.update(mutable_state)
        logger.debug("Event '%s' processed; %d rule(s) fired.", event.name, len(fired))
        return fired

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def step(self) -> tuple[Dict[str, Any], List[Rule]]:
        """Advance the simulation by one tick.

        Calls :meth:`~simulator.Simulator.tick`, updates the twin's state with
        the new sensor readings, then processes every emitted event through the
        ECA engine.

        Returns:
            A tuple ``(readings, fired_rules)`` where:
            - *readings* is the raw sensor data for this tick.
            - *fired_rules* is the flattened list of rules that fired.
        """
        readings, events = self._simulator.tick()
        self._state_manager.update(readings)
        fired_rules: List[Rule] = []
        for event in events:
            mutable_state = self._state_manager.current
            newly_fired = self._engine.process(event, mutable_state)
            self._state_manager.update(mutable_state)
            fired_rules.extend(newly_fired)
        return readings, fired_rules

    def run(self, steps: int) -> List[Dict[str, Any]]:
        """Run the simulation for *steps* ticks.

        Args:
            steps: Number of simulation steps to execute.

        Returns:
            A list of state snapshots (one per step).
        """
        snapshots: List[Dict[str, Any]] = []
        for _ in range(steps):
            self.step()
            snapshots.append(self._state_manager.current)
        logger.info("Simulation ran for %d steps.", steps)
        return snapshots

    # ------------------------------------------------------------------
    # Synchronisation with a physical system
    # ------------------------------------------------------------------

    def sync(self, sensor_data: Dict[str, Any]) -> None:
        """Synchronise the twin with real sensor data from the physical system.

        This method is the primary integration point for live deployments.
        Implementations that connect to real hardware should call this method
        whenever new telemetry arrives.

        Args:
            sensor_data: A flat dict mapping sensor names to their current
                values (e.g. ``{"temperature": 72.3, "pressure": 1.1}``).
        """
        self._state_manager.update(sensor_data)
        # Emit a generic "sync" event carrying the full payload
        sync_event = Event(
            name="sync",
            payload=dict(sensor_data),
            source="physical_system",
        )
        mutable_state = self._state_manager.current
        self._engine.process(sync_event, mutable_state)
        self._state_manager.update(mutable_state)
        logger.info("Twin '%s' synchronised with physical data: %s", self.name, sensor_data)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a human-readable summary of the twin's current status."""
        state = self.state
        lines = [
            f"Digital Twin: {self.name}",
            f"  Simulator tick: {self._simulator.tick_count}",
            f"  State history depth: {len(self.history)}",
            f"  Rules registered: {len(self.rules)}",
            f"  Actions fired (total): {len(self.fired_log)}",
            "  Current state:",
        ]
        for key, value in state.items():
            if not key.startswith("_"):
                lines.append(f"    {key}: {value}")
        return "\n".join(lines)
