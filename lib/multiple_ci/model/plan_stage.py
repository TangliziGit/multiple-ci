from enum import Enum

class PlanState(Enum):
    running = 1
    failure = 2
    success = 3
    canceled = 4
