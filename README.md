# digital-twin-group-3 – ECA Digital Twin

A Python implementation of a **digital twin** for an **Event-Condition-Action (ECA)** system.

## Overview

A digital twin is a live, software-based replica of a physical system that
mirrors its state, can simulate its behaviour, and can react to real-time
sensor data.

This implementation models an electro-mechanical ECA system — a system whose
behaviour is governed by **Event-Condition-Action rules**:

| Concept | Description |
|---------|-------------|
| **Event** | Something that occurs in or around the physical system (e.g. a sensor reading that crosses a threshold). |
| **Condition** | A predicate evaluated against the event's payload; must be `True` for the rule to fire. |
| **Action** | A side-effecting operation executed when its paired condition is met (e.g. updating twin state, raising an alert). |
| **Rule** | Binds an event type to a condition and an action. |

## Project Structure

```
digital-twin-group-3/
├── eca_digital_twin/        # Main package
│   ├── __init__.py
│   ├── eca_model.py         # Event, Condition, Action, Rule, ECAEngine
│   ├── state_manager.py     # StateManager – live state + history
│   ├── simulator.py         # Simulator – synthetic sensor data
│   └── digital_twin.py      # DigitalTwin – orchestrator
├── tests/
│   ├── test_eca_model.py
│   ├── test_state_manager.py
│   ├── test_simulator.py
│   └── test_digital_twin.py
├── main.py                  # Demo / entry point
├── requirements.txt
└── README.md
```

## Quick Start

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the demo

```bash
python main.py
```

### Run tests

```bash
pytest --cov=eca_digital_twin tests/
```

## Usage

```python
from eca_digital_twin import DigitalTwin, Rule, Condition, Action, Event

# Create a twin
twin = DigitalTwin(
    name="eca_system",
    initial_state={"temperature": 25.0, "status": "nominal"},
)

# Add an ECA rule
twin.add_rule(Rule(
    event_name="temperature_changed",
    condition=Condition(
        lambda e: e.payload.get("value", 0) > 80,
        description="temperature > 80 deg C",
    ),
    action=Action(
        lambda e, s: s.update({"status": "OVERHEATING"}),
        name="overheat_alert",
    ),
    name="overheat_rule",
))

# Run the built-in simulator
twin.run(steps=100)

# Or synchronise with real sensor data
twin.sync({"temperature": 92.0, "pressure": 1.1})

# Inspect state
print(twin.state)
print(twin.summary())
```

## Architecture

```
Physical System
      |
      | (sensor telemetry)
      v
  DigitalTwin.sync()
      |
      +---> StateManager   (updates live state + history)
      |
      +---> ECAEngine.process()
               |
               +-- Rule 1 -> Condition -> Action
               +-- Rule 2 -> Condition -> Action
               +-- ...
```

When hardware is unavailable the built-in `Simulator` generates synthetic
readings using mean-reverting random walks, allowing development and testing
without a physical device.
