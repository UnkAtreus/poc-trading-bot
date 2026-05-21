from __future__ import annotations

from enum import Enum


class State(str, Enum):
    IDLE = "IDLE"
    ENTRY_PENDING = "ENTRY_PENDING"
    IN_POSITION_TP_PENDING = "IN_POSITION_TP_PENDING"
    MERGE_PENDING = "MERGE_PENDING"
    # Terminal state for positions whose remainder is below the exchange's
    # min notional/qty so no exit order can be placed. Position stays open
    # and must be flattened manually by the operator.
    DUST_STRANDED = "DUST_STRANDED"
    HALTED = "HALTED"
