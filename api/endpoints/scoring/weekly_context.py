"""Private per-invocation rules value; never a service or transaction cache."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class _WeeklyRulesContext:
    league_id: int
    week_number: int
    conn: object
    rules: Mapping[str, Any]

    def __post_init__(self):
        # resolve_rules currently returns scalars only, so a mapping copy isolates
        # both caller mutation and attempts to change rules through this context.
        object.__setattr__(self, 'rules', MappingProxyType(dict(self.rules)))

    def require_match(self, league_id, week_number, conn):
        if self.league_id != league_id or self.week_number != week_number or self.conn is not conn:
            raise ValueError('Weekly scoring context does not match this call')
