from enum import Enum

class JobState(Enum):
    waiting = 1
    running = 2
    done = 3
    canceled = 4
