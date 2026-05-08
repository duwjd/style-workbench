from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from style_workbench.domain.evaluation.criteria import PASS_THRESHOLD


@dataclass(frozen=True)
class DimensionScore:
    name: str
    score: float  # 0.0 ~ 1.0
    rationale: str


@dataclass
class EvaluationResult:
    id: str
    node_execution_id: str
    evaluator_model: str
    dimensions: list[DimensionScore]
    notable_issues: list[str]
    retry_guidance: str | None
    created_at: datetime

    @property
    def overall_passed(self) -> bool:
        if not self.dimensions:
            return False
        return all(d.score >= PASS_THRESHOLD for d in self.dimensions)

    @property
    def overall_result(self) -> str:
        """DB persist용. "passed" 또는 "failed"."""
        return "passed" if self.overall_passed else "failed"

    @property
    def failed_dimensions(self) -> list[str]:
        return [d.name for d in self.dimensions if d.score < PASS_THRESHOLD]
