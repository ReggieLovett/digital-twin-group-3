"""Physical-system simulator for the ECA digital twin.

The :class:`Simulator` generates synthetic sensor readings and state
transitions that mimic how a real ECA (Event-Condition-Action) physical
device would behave over time.  It is used to:

* Drive the digital twin during development and testing when the real
  hardware is unavailable.
* Run what-if scenarios or predictive simulations by fast-forwarding
  the model.

The default behaviour simulates a simple electro-mechanical system with:
  - **temperature** (°C) – random walk with mean-reversion towards 25 °C
  - **pressure** (bar) – random walk with mean-reversion towards 1.0 bar
  - **vibration** (mm/s) – random walk, clipped to [0, ∞)
  - **power** (W) – random walk, clipped to [0, ∞)

Custom variable configurations can be injected at construction time.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .eca_model import Event

logger = logging.getLogger(__name__)


@dataclass
class VariableConfig:
    """Configuration for a single simulated physical variable.

    Attributes:
        name: Variable identifier used in state and event payloads.
        initial: Starting value.
        mean: Target value for mean-reversion.
        reversion_rate: Fraction pulled toward *mean* each tick (0–1).
        noise_std: Standard deviation of Gaussian noise added each tick.
        min_value: Hard lower bound (``None`` for no bound).
        max_value: Hard upper bound (``None`` for no bound).
        event_threshold: If the absolute change exceeds this, emit an event.
        event_name: Template for the event name; ``"{name}"`` is replaced with
            the variable name.
    """

    name: str
    initial: float
    mean: float
    reversion_rate: float = 0.05
    noise_std: float = 1.0
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    event_threshold: float = 2.0
    event_name: str = "{name}_changed"


# Default sensor variables that represent a generic electro-mechanical system
DEFAULT_VARIABLES: List[VariableConfig] = [
    VariableConfig(
        name="temperature",
        initial=25.0,
        mean=25.0,
        noise_std=0.5,
        min_value=0.0,
        max_value=150.0,
        event_threshold=3.0,
        event_name="{name}_changed",
    ),
    VariableConfig(
        name="pressure",
        initial=1.0,
        mean=1.0,
        noise_std=0.05,
        min_value=0.0,
        max_value=10.0,
        event_threshold=0.2,
        event_name="{name}_changed",
    ),
    VariableConfig(
        name="vibration",
        initial=0.1,
        mean=0.1,
        noise_std=0.02,
        min_value=0.0,
        event_threshold=0.1,
        event_name="{name}_changed",
    ),
    VariableConfig(
        name="power",
        initial=100.0,
        mean=100.0,
        noise_std=5.0,
        min_value=0.0,
        event_threshold=10.0,
        event_name="{name}_changed",
    ),
]


class Simulator:
    """Generates synthetic sensor readings for the ECA physical system.

    Args:
        variables: List of :class:`VariableConfig` objects describing each
            simulated variable.  Defaults to :data:`DEFAULT_VARIABLES`.
        seed: Optional random seed for reproducible simulations.

    Example::

        sim = Simulator(seed=42)
        for _ in range(10):
            readings, events = sim.tick()
            print(readings)
    """

    def __init__(
        self,
        variables: Optional[List[VariableConfig]] = None,
        seed: Optional[int] = None,
    ) -> None:
        self._vars: List[VariableConfig] = variables if variables is not None else list(DEFAULT_VARIABLES)
        self._rng = random.Random(seed)
        self._state: Dict[str, float] = {v.name: v.initial for v in self._vars}
        self._tick_count: int = 0

    @property
    def state(self) -> Dict[str, float]:
        """Current simulated sensor values (read-only copy)."""
        return dict(self._state)

    @property
    def tick_count(self) -> int:
        """Number of ticks elapsed since the simulator was created."""
        return self._tick_count

    def tick(self) -> tuple[Dict[str, Any], List[Event]]:
        """Advance the simulation by one time step.

        Returns:
            A tuple of ``(readings, events)`` where:
            - *readings* is a ``{variable_name: new_value}`` dict.
            - *events* is a list of :class:`~eca_model.Event` objects emitted
              because a variable changed by more than its threshold.
        """
        events: List[Event] = []
        readings: Dict[str, Any] = {}

        for cfg in self._vars:
            old_value = self._state[cfg.name]
            # Mean-reversion + Gaussian noise
            reversion = cfg.reversion_rate * (cfg.mean - old_value)
            noise = self._rng.gauss(0, cfg.noise_std)
            new_value = old_value + reversion + noise

            # Apply bounds
            if cfg.min_value is not None:
                new_value = max(cfg.min_value, new_value)
            if cfg.max_value is not None:
                new_value = min(cfg.max_value, new_value)

            self._state[cfg.name] = new_value
            readings[cfg.name] = new_value

            # Emit event if change exceeds threshold
            if abs(new_value - old_value) >= cfg.event_threshold:
                event_name = cfg.event_name.format(name=cfg.name)
                events.append(
                    Event(
                        name=event_name,
                        payload={
                            "variable": cfg.name,
                            "value": new_value,
                            "previous_value": old_value,
                            "tick": self._tick_count,
                        },
                        source="simulator",
                    )
                )
                logger.debug(
                    "Event emitted: %s (%.3f -> %.3f)", event_name, old_value, new_value
                )

        self._tick_count += 1
        return readings, events

    def run(self, steps: int) -> List[tuple[Dict[str, Any], List[Event]]]:
        """Run the simulator for *steps* ticks and return all results.

        Args:
            steps: Number of simulation steps to execute.

        Returns:
            A list of ``(readings, events)`` tuples, one per tick.
        """
        return [self.tick() for _ in range(steps)]

    def reset(self) -> None:
        """Reset the simulator to its initial state."""
        self._state = {v.name: v.initial for v in self._vars}
        self._tick_count = 0
        logger.info("Simulator reset.")
