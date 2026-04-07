"""Tests for the ECA rules engine (eca_model.py)."""

import pytest
from eca_digital_twin.eca_model import Action, Condition, ECAEngine, Event, Rule


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class TestEvent:
    def test_event_creation(self):
        event = Event(name="test", payload={"value": 42}, source="sensor_1")
        assert event.name == "test"
        assert event.payload == {"value": 42}
        assert event.source == "sensor_1"

    def test_event_defaults(self):
        event = Event(name="simple")
        assert event.payload == {}
        assert event.source is None

    def test_event_repr(self):
        event = Event(name="ping", source="src")
        assert "ping" in repr(event)
        assert "src" in repr(event)


# ---------------------------------------------------------------------------
# Condition
# ---------------------------------------------------------------------------

class TestCondition:
    def test_condition_true(self):
        cond = Condition(lambda e: e.payload.get("value", 0) > 10)
        assert cond.evaluate(Event("x", {"value": 20})) is True

    def test_condition_false(self):
        cond = Condition(lambda e: e.payload.get("value", 0) > 10)
        assert cond.evaluate(Event("x", {"value": 5})) is False

    def test_condition_exception_returns_false(self):
        cond = Condition(lambda e: 1 / 0)  # always raises ZeroDivisionError
        assert cond.evaluate(Event("x")) is False

    def test_condition_description(self):
        cond = Condition(lambda e: True, description="always true")
        assert "always true" in repr(cond)


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------

class TestAction:
    def test_action_executes(self):
        side_effects = []
        action = Action(lambda e, s: side_effects.append(e.name), name="collector")
        action.execute(Event("my_event"), {})
        assert side_effects == ["my_event"]

    def test_action_modifies_state(self):
        action = Action(lambda e, s: s.update({"fired": True}), name="flag")
        state: dict = {}
        action.execute(Event("x"), state)
        assert state["fired"] is True

    def test_action_exception_does_not_propagate(self):
        action = Action(lambda e, s: (_ for _ in ()).throw(RuntimeError("boom")), name="bad")
        # Should not raise
        action.execute(Event("x"), {})


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------

class TestRule:
    def _make_rule(self, event_name="temperature_high"):
        return Rule(
            event_name=event_name,
            condition=Condition(lambda e: True),
            action=Action(lambda e, s: None),
            name="test_rule",
        )

    def test_rule_matches_exact_name(self):
        rule = self._make_rule("temperature_high")
        assert rule.matches(Event("temperature_high")) is True
        assert rule.matches(Event("pressure_low")) is False

    def test_rule_matches_wildcard(self):
        rule = self._make_rule("*")
        assert rule.matches(Event("anything")) is True
        assert rule.matches(Event("other")) is True

    def test_rule_disabled_does_not_match(self):
        rule = self._make_rule("temperature_high")
        rule.enabled = False
        assert rule.matches(Event("temperature_high")) is False

    def test_rule_repr(self):
        rule = self._make_rule()
        assert "test_rule" in repr(rule)


# ---------------------------------------------------------------------------
# ECAEngine
# ---------------------------------------------------------------------------

class TestECAEngine:
    def _engine_with_alert_rule(self):
        engine = ECAEngine()
        state: dict = {}
        fired_names: list = []

        def action_handler(event, s):
            s["alert"] = True
            fired_names.append(event.name)

        rule = Rule(
            event_name="high_temp",
            condition=Condition(lambda e: e.payload.get("value", 0) > 80),
            action=Action(action_handler, name="alert"),
            name="overheat",
        )
        engine.add_rule(rule)
        return engine, state, fired_names

    def test_rule_fires_when_condition_met(self):
        engine, state, fired_names = self._engine_with_alert_rule()
        fired = engine.process(Event("high_temp", {"value": 95}), state)
        assert len(fired) == 1
        assert fired[0].name == "overheat"
        assert state.get("alert") is True

    def test_rule_does_not_fire_when_condition_not_met(self):
        engine, state, _ = self._engine_with_alert_rule()
        fired = engine.process(Event("high_temp", {"value": 50}), state)
        assert fired == []
        assert "alert" not in state

    def test_wrong_event_name_does_not_fire(self):
        engine, state, _ = self._engine_with_alert_rule()
        fired = engine.process(Event("low_temp", {"value": 95}), state)
        assert fired == []

    def test_fired_log_grows(self):
        engine, state, _ = self._engine_with_alert_rule()
        engine.process(Event("high_temp", {"value": 95}), state)
        engine.process(Event("high_temp", {"value": 100}), state)
        assert len(engine.fired_log) == 2

    def test_remove_rule(self):
        engine, state, _ = self._engine_with_alert_rule()
        removed = engine.remove_rule("overheat")
        assert removed is True
        fired = engine.process(Event("high_temp", {"value": 95}), state)
        assert fired == []

    def test_remove_nonexistent_rule_returns_false(self):
        engine = ECAEngine()
        assert engine.remove_rule("ghost") is False

    def test_multiple_rules_evaluated(self):
        engine = ECAEngine()
        results = []

        for letter in "abc":
            engine.add_rule(
                Rule(
                    event_name="tick",
                    condition=Condition(lambda e, l=letter: True),
                    action=Action(lambda e, s, l=letter: results.append(l), name=letter),
                    name=letter,
                )
            )

        engine.process(Event("tick"), {})
        assert results == ["a", "b", "c"]
