#!/usr/bin/env python3
import enum
import time
from threading import Lock

class DoorLockState(enum.Enum):
    LOCKED = enum.auto()
    UNLOCKED = enum.auto()

_lock = Lock()

class DoorLock:
    LOCK_UNLOCK_LOOP_TIMEOUT = 3.0
    LOADING_BAR_LENGTH = 20

    def __init__(self, initial: DoorLockState = DoorLockState.LOCKED):
        self.state = initial

    def _lock(self) -> bool:
        self.state = DoorLockState.LOCKED
        print('Door locked')
        return True

    def _unlock(self) -> bool:
        self.state = DoorLockState.UNLOCKED
        print('Door unlocked')
        return True

    def _busywait(self):
        start = time.monotonic()
        end = start + self.LOCK_UNLOCK_LOOP_TIMEOUT
        while time.monotonic() < end:
            print('.', end='')
            time.sleep(self.LOCK_UNLOCK_LOOP_TIMEOUT / self.LOADING_BAR_LENGTH)
        print()

    def unlock_lock(self) -> bool:
        with _lock:
            ret = self._unlock()
            self._busywait()
            ret &= self._lock()
