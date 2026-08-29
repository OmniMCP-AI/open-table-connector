"""Provider-neutral prepared temporal query result."""

from __future__ import annotations

from dataclasses import dataclass

from .plan import PortableTemporalPlan


@dataclass(frozen=True, slots=True)
class PreparedTemporalQuery:
    statement: str
    parameters: tuple[object, ...]
    residual_plan: PortableTemporalPlan | None

    def __post_init__(self) -> None:
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ValueError("statement must be a non-empty string")
        object.__setattr__(self, "statement", self.statement.strip())
        object.__setattr__(self, "parameters", tuple(self.parameters))
        if self.residual_plan is not None and not isinstance(
            self.residual_plan, PortableTemporalPlan
        ):
            raise TypeError("residual_plan must be a PortableTemporalPlan")


__all__ = ["PreparedTemporalQuery"]
