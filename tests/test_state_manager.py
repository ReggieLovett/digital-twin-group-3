"""Tests for the StateManager."""

import pytest
from eca_digital_twin.state_manager import StateManager


class TestStateManagerInit:
    def test_initial_state_stored(self):
        sm = StateManager({"temperature": 20.0})
        assert sm.get("temperature") == 20.0

    def test_empty_initial_state(self):
        sm = StateManager()
        # current should be empty (no user-provided keys)
        state = sm.current
        assert all(k.startswith("_") for k in state)

    def test_history_has_one_entry_after_init(self):
        sm = StateManager({"x": 1})
        assert len(sm.history) == 1


class TestStateManagerUpdate:
    def test_update_changes_state(self):
        sm = StateManager({"temperature": 20.0})
        sm.update({"temperature": 30.0})
        assert sm.get("temperature") == 30.0

    def test_update_adds_new_key(self):
        sm = StateManager()
        sm.update({"pressure": 1.5})
        assert sm.get("pressure") == 1.5

    def test_update_appends_history(self):
        sm = StateManager({"x": 1})
        sm.update({"x": 2})
        sm.update({"x": 3})
        assert len(sm.history) == 3

    def test_empty_update_does_not_append_history(self):
        sm = StateManager({"x": 1})
        sm.update({})
        assert len(sm.history) == 1

    def test_history_is_immutable_copy(self):
        sm = StateManager({"x": 1})
        sm.update({"x": 2})
        history = sm.history
        history[0]["x"] = 999  # mutating returned copy should not affect internal history
        assert sm.history[0].get("x") == 1


class TestStateManagerReset:
    def test_reset_replaces_state(self):
        sm = StateManager({"x": 1})
        sm.reset({"y": 2})
        assert sm.get("x") is None
        assert sm.get("y") == 2

    def test_reset_appends_history(self):
        sm = StateManager({"x": 1})
        sm.reset({"y": 2})
        assert len(sm.history) == 2


class TestStateManagerSnapshotAt:
    def test_snapshot_at_negative_index(self):
        sm = StateManager({"x": 1})
        sm.update({"x": 2})
        snap = sm.snapshot_at(-1)
        assert snap["x"] == 2

    def test_snapshot_at_zero(self):
        sm = StateManager({"x": 1})
        snap = sm.snapshot_at(0)
        assert snap["x"] == 1


class TestStateManagerDiff:
    def test_diff_detects_changed_value(self):
        sm = StateManager({"x": 1, "y": 10})
        sm.update({"x": 2})
        diff = sm.diff()
        assert "x" in diff
        assert diff["x"] == (1, 2)

    def test_diff_ignores_unchanged_value(self):
        sm = StateManager({"x": 1, "y": 10})
        sm.update({"x": 2})
        diff = sm.diff()
        assert "y" not in diff

    def test_diff_detects_new_key(self):
        sm = StateManager({"x": 1})
        sm.update({"z": 99})
        diff = sm.diff()
        assert "z" in diff
        assert diff["z"] == (None, 99)
