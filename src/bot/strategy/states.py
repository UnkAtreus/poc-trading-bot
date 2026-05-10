from __future__ import annotations

from enum import Enum


class State(str, Enum):
    IDLE = "IDLE"
    ENTRY_PENDING = "ENTRY_PENDING"
    IN_POSITION_TP_PENDING = "IN_POSITION_TP_PENDING"
    MERGE_PENDING = "MERGE_PENDING"
    HALTED = "HALTED"
