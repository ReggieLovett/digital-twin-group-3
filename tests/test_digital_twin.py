"""Tests for the DigitalTwin orchestrator."""

import pytest
from eca_digital_twin import Action, Condition, DigitalTwin, Event, Rule
from eca_digital_twin.simulator import Simulator, VariableConfig


def _make_alert_rule(name="alert_rule", event_name="temperature_changed", threshold=80):
    """Helper: create a rule that sets state['alert'] when value > threshold."""
    return Rule(
        event_name=event_name,
        condition=Condition(lambda e, t=threshold: e.payload.get("value", 0) > t),
        action=Action(lambda e, s: s.update({"alert": True}), name="set_alert"),
        name=name,
    )


class TestDigitalTwinInit:
    def test_default_creation(self):
        twin = DigitalTwin(name="test_twin")
        assert twin.name == "test_twin"
        assert isinstance(twin.state, dict)

    def test_initial_state_passed_through(self):
        twin = DigitalTwin(initial_state={"temperature": 25.0})
        assert twin.state["temperature"] == 25.0

    def test_rules_empty_on_init(self):
        twin = DigitalTwin()
        assert twin.rules == []

    def test_fired_log_empty_on_init(self):
        twin = DigitalTwin()
        assert twin.fired_log == []


class TestDigitalTwinRuleManagement:
    def test_add_rule(self):
        twin = DigitalTwin()
        twin.add_rule(_make_alert_rule())
        assert len(twin.rules) == 1

    def test_remove_rule(self):
        twin = DigitalTwin()
        twin.add_rule(_make_alert_rule(name="r1"))
        removed = twin.remove_rule("r1")
        assert removed is True
        assert len(twin.rules) == 0

    def test_remove_nonexistent_rule(self):
        twin = DigitalTwin()
        assert twin.remove_rule("ghost") is False


class TestDigitalTwinIngest:
    def test_ingest_fires_matching_rule(self):
        twin = DigitalTwin()
        twin.add_rule(_make_alert_rule())
        fired = twin.ingest(Event("temperature_changed", {"value": 95}))
        assert len(fired) == 1
        assert twin.state.get("alert") is True

    def test_ingest_does_not_fire_unmatching_rule(self):
        twin = DigitalTwin()
        twin.add_rule(_make_alert_rule())
        fired = twin.ingest(Event("temperature_changed", {"value": 50}))
        assert fired == []
        assert "alert" not in twin.state

    def test_ingest_updates_fired_log(self):
        twin = DigitalTwin()
        twin.add_rule(_make_alert_rule())
        twin.ingest(Event("temperature_changed", {"value": 95}))
        assert len(twin.fired_log) == 1

    def test_ingest_preserves_history(self):
        twin = DigitalTwin(initial_state={"temperature": 20.0})
        twin.ingest(Event("temperature_changed", {"value": 95}))
        assert len(twin.history) >= 2


class TestDigitalTwinStep:
    def test_step_returns_readings_and_rules(self):
        sim = Simulator(seed=0)
        twin = DigitalTwin(simulator=sim)
        readings, fired = twin.step()
        assert isinstance(readings, dict)
        assert isinstance(fired, list)

    def test_step_updates_state(self):
        sim = Simulator(seed=42)
        twin = DigitalTwin(initial_state={}, simulator=sim)
        twin.step()
        # After one step the state should contain sensor values
        assert "temperature" in twin.state

    def test_step_fires_rules_on_events(self):
        # Create a variable that always emits an event
        cfg = VariableConfig(
            name="spike",
            initial=0.0,
            mean=1000.0,
            noise_std=0.0,
            reversion_rate=1.0,
            event_threshold=0.1,
            event_name="spike_changed",
        )
        sim = Simulator(variables=[cfg], seed=0)
        twin = DigitalTwin(simulator=sim)
        twin.add_rule(
            Rule(
                event_name="spike_changed",
                condition=Condition(lambda e: True),
                action=Action(lambda e, s: s.update({"spiked": True}), name="mark_spike"),
                name="spike_rule",
            )
        )
        _, fired = twin.step()
        assert len(fired) == 1
        assert twin.state.get("spiked") is True


class TestDigitalTwinRun:
    def test_run_returns_snapshots(self):
        twin = DigitalTwin(simulator=Simulator(seed=0))
        snapshots = twin.run(5)
        assert len(snapshots) == 5

    def test_run_all_snapshots_are_dicts(self):
        twin = DigitalTwin(simulator=Simulator(seed=0))
        for snap in twin.run(3):
            assert isinstance(snap, dict)


class TestDigitalTwinSync:
    def test_sync_updates_state(self):
        twin = DigitalTwin(initial_state={"temperature": 20.0})
        twin.sync({"temperature": 50.0, "pressure": 1.2})
        assert twin.state["temperature"] == 50.0
        assert twin.state["pressure"] == 1.2

    def test_sync_fires_sync_rule(self):
        twin = DigitalTwin()
        fired_events = []
        twin.add_rule(
            Rule(
                event_name="sync",
                condition=Condition(lambda e: True),
                action=Action(lambda e, s: fired_events.append(e.name), name="record"),
                name="sync_listener",
            )
        )
        twin.sync({"temperature": 30.0})
        assert "sync" in fired_events


class TestDigitalTwinSummary:
    def test_summary_contains_name(self):
        twin = DigitalTwin(name="my_twin")
        assert "my_twin" in twin.summary()

    def test_summary_is_string(self):
        twin = DigitalTwin()
        assert isinstance(twin.summary(), str)
