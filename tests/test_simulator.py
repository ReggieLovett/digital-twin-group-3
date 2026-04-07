"""Tests for the Simulator."""

import pytest
from eca_digital_twin.simulator import Simulator, VariableConfig


class TestSimulatorInit:
    def test_default_variables_present(self):
        sim = Simulator(seed=0)
        state = sim.state
        assert "temperature" in state
        assert "pressure" in state
        assert "vibration" in state
        assert "power" in state

    def test_custom_variable(self):
        cfg = VariableConfig(name="voltage", initial=5.0, mean=5.0, noise_std=0.1)
        sim = Simulator(variables=[cfg], seed=0)
        assert "voltage" in sim.state

    def test_initial_tick_count(self):
        sim = Simulator(seed=0)
        assert sim.tick_count == 0


class TestSimulatorTick:
    def test_tick_returns_readings_and_events(self):
        sim = Simulator(seed=1)
        readings, events = sim.tick()
        assert isinstance(readings, dict)
        assert isinstance(events, list)

    def test_tick_increments_tick_count(self):
        sim = Simulator(seed=0)
        sim.tick()
        assert sim.tick_count == 1
        sim.tick()
        assert sim.tick_count == 2

    def test_readings_keys_match_variables(self):
        sim = Simulator(seed=0)
        readings, _ = sim.tick()
        assert set(readings.keys()) == {"temperature", "pressure", "vibration", "power"}

    def test_min_bound_respected(self):
        cfg = VariableConfig(
            name="val",
            initial=0.0,
            mean=0.0,
            noise_std=100.0,  # large noise
            min_value=0.0,
        )
        sim = Simulator(variables=[cfg], seed=42)
        for _ in range(50):
            readings, _ = sim.tick()
            assert readings["val"] >= 0.0

    def test_max_bound_respected(self):
        cfg = VariableConfig(
            name="val",
            initial=150.0,
            mean=150.0,
            noise_std=100.0,
            max_value=150.0,
        )
        sim = Simulator(variables=[cfg], seed=42)
        for _ in range(50):
            readings, _ = sim.tick()
            assert readings["val"] <= 150.0

    def test_event_emitted_on_large_change(self):
        cfg = VariableConfig(
            name="spike",
            initial=0.0,
            mean=1000.0,  # strong pull away from initial
            noise_std=0.0,
            reversion_rate=1.0,  # jump all the way in one tick
            event_threshold=0.1,
            event_name="{name}_changed",
        )
        sim = Simulator(variables=[cfg], seed=0)
        _, events = sim.tick()
        assert len(events) == 1
        assert events[0].name == "spike_changed"

    def test_reproducible_with_seed(self):
        sim1 = Simulator(seed=99)
        sim2 = Simulator(seed=99)
        readings1, _ = sim1.tick()
        readings2, _ = sim2.tick()
        assert readings1 == readings2


class TestSimulatorRun:
    def test_run_returns_correct_number_of_results(self):
        sim = Simulator(seed=0)
        results = sim.run(5)
        assert len(results) == 5

    def test_run_advances_tick_count(self):
        sim = Simulator(seed=0)
        sim.run(10)
        assert sim.tick_count == 10


class TestSimulatorReset:
    def test_reset_restores_initial_state(self):
        sim = Simulator(seed=0)
        initial = sim.state.copy()
        sim.run(20)
        sim.reset()
        assert sim.state == initial

    def test_reset_restores_tick_count(self):
        sim = Simulator(seed=0)
        sim.run(5)
        sim.reset()
        assert sim.tick_count == 0
