"""ECA Digital Twin package.

This package implements a digital twin for an Event-Condition-Action (ECA)
system. The digital twin mirrors a physical system by:
  - Maintaining a synchronized state representation
  - Evaluating ECA rules when events arrive
  - Simulating physical behaviour for prediction and testing
"""

from .eca_model import Event, Condition, Action, Rule, ECAEngine
from .state_manager import StateManager
from .simulator import Simulator
from .digital_twin import DigitalTwin

__all__ = [
    "Event",
    "Condition",
    "Action",
    "Rule",
    "ECAEngine",
    "StateManager",
    "Simulator",
    "DigitalTwin",
]
