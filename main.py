"""ECA Digital Twin – demo entry point.

Run with::

    python main.py

This script demonstrates the digital twin by:
1. Creating a twin of a simple electro-mechanical ECA system.
2. Registering ECA rules for temperature, pressure, and vibration monitoring.
3. Running the built-in simulator for a number of steps.
4. Printing a summary of the twin's final state.
"""

import logging

from eca_digital_twin import Action, Condition, DigitalTwin, Event, Rule
from eca_digital_twin.simulator import Simulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def build_twin() -> DigitalTwin:
    """Construct and return a pre-configured ECA digital twin."""
    sim = Simulator(seed=42)
    twin = DigitalTwin(
        name="eca_system",
        initial_state={
            "temperature": 25.0,
            "pressure": 1.0,
            "vibration": 0.1,
            "power": 100.0,
            "alert": None,
            "status": "nominal",
        },
        simulator=sim,
    )

    # ------------------------------------------------------------------
    # Rule 1 – overheat alert (fires on both temperature_changed and sync)
    # ------------------------------------------------------------------
    for event_name in ("temperature_changed", "sync"):
        twin.add_rule(
            Rule(
                event_name=event_name,
                condition=Condition(
                    lambda e: e.payload.get("temperature", e.payload.get("value", 0)) > 35,
                    description="temperature > 35°C",
                ),
                action=Action(
                    lambda e, s: s.update(
                        {"alert": "OVERHEAT", "status": "warning"}
                    ),
                    name="raise_overheat_alert",
                ),
                name=f"overheat_rule_{event_name}",
            )
        )

    # ------------------------------------------------------------------
    # Rule 2 – high-pressure alert
    # ------------------------------------------------------------------
    for event_name in ("pressure_changed", "sync"):
        twin.add_rule(
            Rule(
                event_name=event_name,
                condition=Condition(
                    lambda e: e.payload.get("pressure", e.payload.get("value", 0)) > 1.5,
                    description="pressure > 1.5 bar",
                ),
                action=Action(
                    lambda e, s: s.update(
                        {"alert": "HIGH_PRESSURE", "status": "warning"}
                    ),
                    name="raise_pressure_alert",
                ),
                name=f"high_pressure_rule_{event_name}",
            )
        )

    # ------------------------------------------------------------------
    # Rule 3 – excessive vibration alert
    # ------------------------------------------------------------------
    for event_name in ("vibration_changed", "sync"):
        twin.add_rule(
            Rule(
                event_name=event_name,
                condition=Condition(
                    lambda e: e.payload.get("vibration", e.payload.get("value", 0)) > 0.5,
                    description="vibration > 0.5 mm/s",
                ),
                action=Action(
                    lambda e, s: s.update(
                        {"alert": "VIBRATION", "status": "warning"}
                    ),
                    name="raise_vibration_alert",
                ),
                name=f"vibration_rule_{event_name}",
            )
        )

    # ------------------------------------------------------------------
    # Rule 4 – clear alert when all readings return to normal (wildcard)
    # ------------------------------------------------------------------
    def _all_clear(event: Event) -> bool:
        p = event.payload
        return (
            p.get("temperature", 999) <= 35
            and p.get("pressure", 999) <= 1.5
            and p.get("vibration", 999) <= 0.5
        )

    twin.add_rule(
        Rule(
            event_name="sync",
            condition=Condition(_all_clear, description="all readings nominal"),
            action=Action(
                lambda e, s: s.update({"alert": None, "status": "nominal"}),
                name="clear_alert",
            ),
            name="all_clear_rule",
        )
    )

    return twin


def main() -> None:
    """Run the ECA digital twin demo."""
    print("=" * 60)
    print("ECA Digital Twin – Demo")
    print("=" * 60)

    twin = build_twin()

    print(f"\nInitial state:\n{twin.summary()}\n")

    # Simulate 50 ticks
    steps = 50
    print(f"Running simulation for {steps} ticks …")
    twin.run(steps)

    # Manually inject a high-temperature sync event to demonstrate rule firing
    print("\nInjecting high-temperature sync event …")
    twin.sync(
        {
            "temperature": 90.0,
            "pressure": 1.0,
            "vibration": 0.1,
            "power": 100.0,
        }
    )

    print(f"\nPost-sync state:\n{twin.summary()}\n")

    print(f"Total actions fired: {len(twin.fired_log)}")
    if twin.fired_log:
        print("Last 5 fired actions:")
        for entry in twin.fired_log[-5:]:
            print(f"  rule={entry['rule']!r}  event={entry['event']!r}")

    print("\nDemo complete.")


if __name__ == "__main__":
    main()
