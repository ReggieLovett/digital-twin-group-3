"""ECA (Event-Condition-Action) rules engine.

This module defines the core building blocks of an ECA system:

* **Event** – something that happens in or around the physical system
  (e.g. a sensor reading, a state transition, a timer tick).
* **Condition** – a callable predicate that decides whether an event should
  trigger an action.
* **Action** – a callable that is executed when the paired condition is met.
* **Rule** – binds an event type to a condition and an action.
* **ECAEngine** – evaluates rules against incoming events and records which
  actions were fired.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Represents an event emitted by the physical (or simulated) system.

    Attributes:
        name: A short identifier for the event type (e.g. ``"temperature_high"``).
        payload: Arbitrary data attached to the event (e.g. sensor readings).
        source: Optional identifier of the component that raised the event.
    """

    name: str
    payload: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None

    def __repr__(self) -> str:
        return f"Event(name={self.name!r}, source={self.source!r}, payload={self.payload})"


class Condition:
    """A callable predicate that evaluates an :class:`Event`.

    Args:
        predicate: A function ``(event: Event) -> bool``.
        description: Human-readable description of the condition.
    """

    def __init__(
        self,
        predicate: Callable[[Event], bool],
        description: str = "",
    ) -> None:
        self._predicate = predicate
        self.description = description

    def evaluate(self, event: Event) -> bool:
        """Return ``True`` if the condition is satisfied for *event*."""
        try:
            result = bool(self._predicate(event))
        except Exception as exc:
            logger.warning("Condition evaluation raised an exception: %s", exc)
            result = False
        return result

    def __repr__(self) -> str:
        return f"Condition({self.description!r})"


class Action:
    """An operation executed when a rule's condition is met.

    Args:
        handler: A function ``(event: Event, state: dict) -> None``.
        name: Short identifier for the action.
    """

    def __init__(
        self,
        handler: Callable[[Event, Dict[str, Any]], None],
        name: str = "",
    ) -> None:
        self._handler = handler
        self.name = name

    def execute(self, event: Event, state: Dict[str, Any]) -> None:
        """Execute the action given the triggering *event* and current *state*."""
        try:
            self._handler(event, state)
        except Exception as exc:
            logger.error("Action %r execution failed: %s", self.name, exc)

    def __repr__(self) -> str:
        return f"Action({self.name!r})"


@dataclass
class Rule:
    """Associates an event type with a condition and an action.

    A rule is triggered when an event whose ``name`` matches *event_name*
    arrives **and** the :class:`Condition` evaluates to ``True``.

    Attributes:
        event_name: The event type this rule listens for.  ``"*"`` matches
            every event.
        condition: The predicate that must hold.
        action: The action to execute when the condition is met.
        name: Optional human-readable label.
        enabled: When ``False`` the rule is skipped during evaluation.
    """

    event_name: str
    condition: Condition
    action: Action
    name: str = ""
    enabled: bool = True

    def matches(self, event: Event) -> bool:
        """Return ``True`` if this rule applies to *event*."""
        if not self.enabled:
            return False
        return self.event_name == "*" or self.event_name == event.name

    def __repr__(self) -> str:
        return (
            f"Rule(name={self.name!r}, event={self.event_name!r}, "
            f"enabled={self.enabled})"
        )


class ECAEngine:
    """Evaluates a set of :class:`Rule` objects against incoming events.

    Example usage::

        engine = ECAEngine()
        engine.add_rule(Rule(
            event_name="temperature_high",
            condition=Condition(lambda e: e.payload.get("value", 0) > 80),
            action=Action(lambda e, s: s.update({"alert": True}), name="set_alert"),
            name="overheat_alert",
        ))

        state = {}
        fired = engine.process(Event("temperature_high", {"value": 95}), state)
    """

    def __init__(self) -> None:
        self._rules: List[Rule] = []
        self._fired_log: List[Dict[str, Any]] = []

    @property
    def rules(self) -> List[Rule]:
        """Read-only view of registered rules."""
        return list(self._rules)

    @property
    def fired_log(self) -> List[Dict[str, Any]]:
        """Log entries for every action that was fired."""
        return list(self._fired_log)

    def add_rule(self, rule: Rule) -> None:
        """Register a new rule."""
        self._rules.append(rule)
        logger.debug("Registered rule: %s", rule)

    def remove_rule(self, name: str) -> bool:
        """Remove the first rule whose ``name`` matches.  Returns ``True`` if found."""
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                del self._rules[i]
                return True
        return False

    def process(self, event: Event, state: Dict[str, Any]) -> List[Rule]:
        """Evaluate all matching rules against *event* and *state*.

        Args:
            event: The incoming event.
            state: The current mutable state dictionary; actions may modify it.

        Returns:
            The list of rules whose actions were fired.
        """
        fired: List[Rule] = []
        for rule in self._rules:
            if not rule.matches(event):
                continue
            if rule.condition.evaluate(event):
                logger.info("Rule %r fired for event %r", rule.name, event.name)
                rule.action.execute(event, state)
                fired.append(rule)
                self._fired_log.append({"rule": rule.name, "event": event.name})
        return fired
