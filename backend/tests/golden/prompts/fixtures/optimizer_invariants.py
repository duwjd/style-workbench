"""Golden fixtures for F02 Prompt Optimizer invariants (spec §10.3).

10 prompt bodies x 5 retry_guidance scenarios = 50 cases.

These fixtures define the *inputs* fed to ``LlmPromptModifier`` and the
*invariants* the modifier's output must satisfy. The invariants are
intentionally NOT exact-string expectations (LLM noise makes that
brittle); they are predicates that any correct edit must satisfy:

* every ``required=true`` placeholder in ``declared_variables`` MUST
  appear literally in ``new_body``;
* no undeclared placeholder may appear in ``new_body``;
* placeholder identifiers MUST NOT be renamed (e.g. ``{role}`` ->
  ``{users_role}``);
* placeholder MUST NOT be substituted with an imagined value (e.g.
  ``{name}`` -> ``홍길동``).

The fixture exposes:

* ``PROMPT_BODIES``   — 10 prompt body strings (mix of node types).
* ``GUIDANCE_SCENARIOS`` — 5 ``(failed_dimensions, retry_guidance)``
  tuples covering image / video / text / composition edits.
* ``CASES`` — Cartesian product of the above as ``OptimizerCase``
  NamedTuples, ready for ``pytest.mark.parametrize``.

Backend-engineer will pair these fixtures with mocked ``ClaudeAdapter``
responses in ``tests/golden/prompts/test_optimizer_invariants.py``.

CLAUDE.md §5 1번 compliance: this module is a pure data fixture and does
NOT import any evaluator or variant-generator prompt strings.
"""

from __future__ import annotations

from typing import Any, NamedTuple

# ---------------------------------------------------------------------------
# 10 prompt bodies — each labelled with intended node_type
# ---------------------------------------------------------------------------


class PromptBody(NamedTuple):
    id: str
    node_type: str  # "text" | "image" | "video" | "composition"
    body: str
    declared_variables: list[dict[str, Any]]


PROMPT_BODIES: list[PromptBody] = [
    # B01 — single required placeholder, image node.
    PromptBody(
        id="B01_image_single_required",
        node_type="image",
        body="Studio headshot of {name}, neutral grey backdrop, soft key light.",
        declared_variables=[
            {"name": "name", "role": "subject_name", "required": True},
        ],
    ),
    # B02 — two required placeholders, image node.
    PromptBody(
        id="B02_image_two_required",
        node_type="image",
        body=(
            "Professional portrait of {name}, role: {role}. Studio backdrop, three-point lighting."
        ),
        declared_variables=[
            {"name": "name", "role": "subject_name", "required": True},
            {"name": "role", "role": "occupation", "required": True},
        ],
    ),
    # B03 — required + optional placeholder, image node.
    PromptBody(
        id="B03_image_required_plus_optional",
        node_type="image",
        body=(
            "Editorial portrait of {name} at {location}, golden hour, "
            "85mm lens, shallow depth of field."
        ),
        declared_variables=[
            {"name": "name", "role": "subject_name", "required": True},
            {"name": "location", "role": "scene_location", "required": False},
        ],
    ),
    # B04 — single placeholder repeated multiple times, text node.
    PromptBody(
        id="B04_text_repeated_placeholder",
        node_type="text",
        body=(
            "Write a one-sentence visual brief for {concept}. "
            "Focus on the mood implied by {concept} and avoid generic adjectives."
        ),
        declared_variables=[
            {"name": "concept", "role": "design_concept", "required": True},
        ],
    ),
    # B05 — text node, no placeholders.
    PromptBody(
        id="B05_text_no_placeholders",
        node_type="text",
        body="Write a single sentence describing a calm coastal sunrise.",
        declared_variables=[],
    ),
    # B06 — text node with Korean body and one placeholder.
    PromptBody(
        id="B06_text_korean_single",
        node_type="text",
        body="다음 인물의 한 줄 비주얼 브리프를 작성하라: {name}.",
        declared_variables=[
            {"name": "name", "role": "subject_name", "required": True},
        ],
    ),
    # B07 — video node, two placeholders.
    PromptBody(
        id="B07_video_two_required",
        node_type="video",
        body=(
            "A 4-second clip of {subject} performing {action}. "
            "Camera pushes in slowly, natural daylight."
        ),
        declared_variables=[
            {"name": "subject", "role": "subject_name", "required": True},
            {"name": "action", "role": "action_description", "required": True},
        ],
    ),
    # B08 — video node, single placeholder + descriptive context.
    PromptBody(
        id="B08_video_single_required",
        node_type="video",
        body=(
            "Slow-motion clip of {product} rotating against a black backdrop. "
            "Soft rim light from upper-left, 5 seconds."
        ),
        declared_variables=[
            {"name": "product", "role": "product_name", "required": True},
        ],
    ),
    # B09 — composition node, mixing two named placeholders.
    PromptBody(
        id="B09_composition_two_required",
        node_type="composition",
        body=(
            "Combine the foreground portrait of {name} with the background plate "
            "showing {scene}. Match lighting direction and color temperature."
        ),
        declared_variables=[
            {"name": "name", "role": "subject_name", "required": True},
            {"name": "scene", "role": "scene_description", "required": True},
        ],
    ),
    # B10 — composition node, single required placeholder.
    PromptBody(
        id="B10_composition_single_required",
        node_type="composition",
        body=(
            "Layer the generated logo of {brand} onto the product mockup. "
            "Preserve perspective and apply subtle shadow consistent with the scene light."
        ),
        declared_variables=[
            {"name": "brand", "role": "brand_name", "required": True},
        ],
    ),
]

assert len(PROMPT_BODIES) == 10, f"Expected 10 prompt bodies, got {len(PROMPT_BODIES)}"


# ---------------------------------------------------------------------------
# 5 retry_guidance scenarios — each spans multiple node types
# ---------------------------------------------------------------------------


class GuidanceScenario(NamedTuple):
    id: str
    failed_dimensions: list[str]
    retry_guidance: dict[str, Any]


GUIDANCE_SCENARIOS: list[GuidanceScenario] = [
    # S01 — lighting fix, common to image and composition.
    GuidanceScenario(
        id="S01_lighting_fix",
        failed_dimensions=["lighting_match"],
        retry_guidance={
            "instruction": (
                "주광원을 좌측 45도에서 우측 정면으로 변경하고 보조광을 약하게 추가하라."
            ),
            "confidence": 0.82,
        },
    ),
    # S02 — composition / framing fix (image, composition).
    GuidanceScenario(
        id="S02_framing_fix",
        failed_dimensions=["composition"],
        retry_guidance={
            "instruction": (
                "주제를 화면 중앙에서 1/3 지점으로 이동하고 상단 여백을 늘려 균형을 잡아라."
            ),
            "confidence": 0.74,
        },
    ),
    # S03 — tone / register fix (text).
    GuidanceScenario(
        id="S03_tone_fix",
        failed_dimensions=["tone_match"],
        retry_guidance={
            "instruction": ("문장의 톤을 더 격식 있고 차분한 어조로 조정하라. 길이는 그대로 유지."),
            "confidence": 0.68,
        },
    ),
    # S04 — motion / temporal fix (video).
    GuidanceScenario(
        id="S04_motion_fix",
        failed_dimensions=["motion_natural", "temporal_consistency"],
        retry_guidance={
            "instruction": (
                "카메라 푸시인 속도를 더 느리게 조정하고 "
                "마지막 1초의 모션을 정지에 가깝게 마무리하라."
            ),
            "confidence": 0.79,
        },
    ),
    # S05 — multi-dimension fix (image/composition).
    GuidanceScenario(
        id="S05_multi_dimension",
        failed_dimensions=["color_tone", "shadow_consistent"],
        retry_guidance={
            "instruction": (
                "전체 톤을 약간 따뜻한 방향으로 보정하고 그림자 방향이 광원과 일치하도록 명시하라."
            ),
            "confidence": 0.71,
        },
    ),
]

assert len(GUIDANCE_SCENARIOS) == 5, f"Expected 5 scenarios, got {len(GUIDANCE_SCENARIOS)}"


# ---------------------------------------------------------------------------
# Cartesian product: 10 x 5 = 50 cases
# ---------------------------------------------------------------------------


class OptimizerCase(NamedTuple):
    """One (prompt_body x guidance_scenario) case.

    Test consumers should:
    1. call ``build_optimizer_user_message(...)`` with these fields,
    2. invoke ``LlmPromptModifier.modify(...)`` (or a stubbed ClaudeAdapter),
    3. assert the resulting ``new_body`` satisfies the placeholder
       invariants documented in this module.
    """

    case_id: str
    node_type: str
    original_body: str
    declared_variables: list[dict[str, Any]]
    failed_dimensions: list[str]
    retry_guidance: dict[str, Any]
    # Convenience pre-computed sets — backend-engineer's test can compare
    # these against extract_placeholders(new_body).
    required_placeholders: frozenset[str]
    allowed_placeholders: frozenset[str]


def _build_cases() -> list[OptimizerCase]:
    cases: list[OptimizerCase] = []
    for body in PROMPT_BODIES:
        required = frozenset(v["name"] for v in body.declared_variables if v.get("required", False))
        allowed = frozenset(v["name"] for v in body.declared_variables)
        for scenario in GUIDANCE_SCENARIOS:
            cases.append(
                OptimizerCase(
                    case_id=f"{body.id}__{scenario.id}",
                    node_type=body.node_type,
                    original_body=body.body,
                    declared_variables=body.declared_variables,
                    failed_dimensions=scenario.failed_dimensions,
                    retry_guidance=scenario.retry_guidance,
                    required_placeholders=required,
                    allowed_placeholders=allowed,
                )
            )
    return cases


CASES: list[OptimizerCase] = _build_cases()
assert len(CASES) == 50, f"Expected 50 cases, got {len(CASES)}"


__all__ = [
    "PromptBody",
    "GuidanceScenario",
    "OptimizerCase",
    "PROMPT_BODIES",
    "GUIDANCE_SCENARIOS",
    "CASES",
]
