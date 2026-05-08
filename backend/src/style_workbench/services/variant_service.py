from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from style_workbench.adapters.base import ModelAdapter, ModelInput
from style_workbench.adapters.registry import get_adapter
from style_workbench.core.errors import DagValidationError
from style_workbench.domain.style.entity import Style
from style_workbench.domain.style.schema import style_from_dict
from style_workbench.domain.style.validation import validate_dag
from style_workbench.infra.repositories.style_repo import StyleRecord, StyleRepository
from style_workbench.prompts.variant_generator import SYSTEM_PROMPT

logger = structlog.get_logger(__name__)


@dataclass
class VariantBrief:
    concept: str
    vertical: str
    tone: str
    step_composition: list[str] = field(default_factory=list)
    input_kinds: list[str] = field(default_factory=list)
    n: int = 5


def _build_user_prompt(brief: VariantBrief) -> str:
    payload: dict[str, Any] = {
        "concept": brief.concept,
        "vertical": brief.vertical,
        "tone": brief.tone,
        "step_composition": brief.step_composition,
        "input_kinds": brief.input_kinds,
        "n": brief.n,
    }
    return "\n".join(
        [json.dumps(payload, ensure_ascii=False), "", f"Generate exactly {brief.n} variants."]
    )


class VariantService:
    def __init__(
        self,
        adapter: ModelAdapter | None = None,
        repo: StyleRepository | None = None,
    ) -> None:
        self._adapter = adapter or get_adapter("anthropic")
        self._repo = repo

    async def generate(
        self,
        brief: VariantBrief,
        *,
        save: bool = False,
    ) -> list[StyleRecord]:
        user_prompt = _build_user_prompt(brief)
        output = await self._adapter.generate(
            ModelInput(
                model_id="claude-sonnet-4-6",
                prompt=user_prompt,
                system=SYSTEM_PROMPT,
                temperature=0.8,
                max_tokens=8192,
            )
        )
        logger.info(
            "variant_generator_response_received",
            response_hash=hash(output.text),
            output_tokens=output.output_tokens,
            cost_usd=output.cost_usd,
        )
        styles = self._parse_response(output.text, brief.concept, brief.vertical)

        if save and self._repo is not None:
            records: list[StyleRecord] = []
            for s in styles:
                record = await self._repo.save(s)
                records.append(record)
            return records

        # repo 없는 경우 — 테스트 호환용 임시 StyleRecord
        now = datetime.now(UTC)
        return [StyleRecord(style=s, version_id="", created_at=now) for s in styles]

    @staticmethod
    def _parse_response(raw: str, concept: str, vertical: str) -> list[Style]:
        match = re.search(r"<variants>(.*?)</variants>", raw, re.DOTALL)
        if match is None:
            raise DagValidationError(
                "Variant Generator response did not contain <variants>...</variants> tag"
            )
        json_text = match.group(1).strip()
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise DagValidationError(f"Failed to parse JSON inside <variants> tag: {exc}") from exc
        if not isinstance(parsed, list):
            raise DagValidationError(
                f"Expected a JSON array inside <variants>, got {type(parsed).__name__}"
            )
        styles: list[Style] = []
        for i, item in enumerate(parsed):
            if not isinstance(item, dict):
                raise DagValidationError(f"Variant at index {i} is not a JSON object")
            try:
                style = style_from_dict(item, concept, vertical)
            except (KeyError, ValueError, TypeError) as exc:
                raise DagValidationError(
                    f"Failed to construct Style from variant at index {i}: {exc}"
                ) from exc
            validate_dag(style.dag)
            styles.append(style)
        return styles
