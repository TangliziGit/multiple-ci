from enum import Enum

class StageState(Enum):
    waiting = 1
    running = 2
    failure = 3
    success = 4
    canceled = 5
