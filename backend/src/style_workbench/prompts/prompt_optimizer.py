# ruff: noqa: E501
#
# This module is dominated by a multi-line system-prompt literal whose
# embedded JSON example must keep specific lines unbroken so the model is
# taught the exact one-line shape it must emit. Wrapping those lines would
# mislead the model. Line-length policy is therefore disabled for this
# file; correctness of the prompt text wins over textual width.

"""F02 Prompt Optimizer — system prompt module.

이 모듈은 ``LlmPromptModifier`` (F02 ``engine/prompt_optimizer.py``)가
Claude Opus 호출 시 사용하는 system / user prompt 빌더를 정의한다.

분리 invariant (CLAUDE.md §5 1번, F02 spec §4 FR-11):

* Variant Generator(``prompts/variant_generator.py``)와 Step
  Evaluator(``prompts/evaluator_*.py``)의 system prompt 문자열을 import
  하거나 substring으로 재사용하지 않는다. Optimizer는 *지시받은 변경만*
  수행하는 별도 역할이며, 결과물의 품질을 평가하지 않는다.

* ``shared/safety.py``의 evaluator용 safety_block 도 재사용하지 않는다
  ─ Optimizer 전용 placeholder 보호 문구를 본 모듈에 직접 작성한다
  (evaluator 문구는 "score / rationale" 어휘에 묶여 있어 Optimizer의
  "본문 편집" 역할과 어울리지 않으며, substring 재사용을 차단해 분리
  invariant를 정적으로 검증 가능하게 한다).

외부 SDK 격리 (CLAUDE.md §5.2, F02 spec §4 FR-10):

* 본 모듈은 단순 문자열·딕셔너리 모듈로, anthropic / openai / replicate
  SDK를 import 하지 않는다. Claude 호출은 ``adapters/claude.py`` 경유만.
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# Model / decoding parameters (F02 spec §4 FR-2)
# ---------------------------------------------------------------------------

# Optimizer 디폴트 모델. Evaluator(claude-opus-4-6)와 다른 버전을 선택해
# 자기확증편향을 한번 더 분리한다 (F02 spec §4 FR-2). 실제 호출 시
# core/config.py의 PROMPT_OPTIMIZER_MODEL 환경변수로 override 가능.
OPTIMIZER_MODEL: str = "claude-opus-4-7"

# 결정적 수정을 위해 낮은 temperature. evaluator(0.0~0.2)와 같은 범위이지만
# 이는 *역할 분리*가 아닌 *결정성 요구*가 같기 때문이다.
TEMPERATURE: float = 0.2

# 출력은 짧은 JSON 객체 1개 — change_summary 1~2문장 + new_body. 입력
# prompt 본문 길이 + 충분한 여유로 1500 토큰.
MAX_TOKENS: int = 1500


# ---------------------------------------------------------------------------
# Node-type guidance (FR-3 — evaluator system prompt를 import 하지 않고
# 사람이 새로 작성한 별도 안내)
# ---------------------------------------------------------------------------

# 각 노드 타입에서 *retry_guidance가 어떤 종류의 변경을 의미하는지* 만 적는다.
# evaluator의 평가 차원 정의를 substring으로 가져오면 안 된다 (분리 invariant).
# 따라서 표현은 의도적으로 evaluator dimension key 와 다른 어휘로 작성한다.
_NODE_TYPE_GUIDANCE: dict[str, str] = {
    "text": (
        "Text node: rewrite wording, sentence length, register, or tone. "
        "Do not invent factual claims that were not in the original body. "
        "Length should stay within ±20% of the original unless the guidance "
        "explicitly asks for expansion or compression."
    ),
    "image": (
        "Image node: adjust descriptive cues for framing, lens, lighting "
        "direction, color palette, background, or subject styling. Keep the "
        "core subject and identity unchanged unless guidance says otherwise. "
        "Do not add medium or model directives that were not implied by the "
        "original body."
    ),
    "video": (
        "Video node: adjust motion direction, camera move, pacing, duration "
        "cues, or temporal continuity hints. Keep the subject and overall "
        "scene unchanged unless guidance says otherwise. Avoid contradictory "
        "motion instructions."
    ),
    "composition": (
        "Composition node: adjust how upstream node outputs are combined — "
        "layout balance, layering order, blending strength, perspective "
        "alignment, or light direction continuity. Do not introduce new "
        "upstream references that are not already wired."
    ),
}

# 알 수 없는 node_type 이 들어와도 안전한 기본 안내.
_DEFAULT_NODE_GUIDANCE: str = (
    "Generic node: apply the smallest edit that addresses the guidance while "
    "preserving the original intent and all placeholders."
)


def _resolve_node_guidance(node_type: str) -> str:
    return _NODE_TYPE_GUIDANCE.get(node_type, _DEFAULT_NODE_GUIDANCE)


# ---------------------------------------------------------------------------
# System prompt (FR-3, FR-4, FR-11)
# ---------------------------------------------------------------------------

# The system prompt contains an embedded JSON example whose `new_body` and
# `change_summary` lines must remain unbroken to teach the model the exact
# expected shape. Wrapping those lines would mislead the model into emitting
# multi-line strings. Keep the noqa scoped to this constant only.
PROMPT_OPTIMIZER_SYSTEM_PROMPT: str = """\

You are a prompt body editor for the Style Workbench. Your single role is
to apply a *targeted edit* to one prompt body so it better satisfies a set
of fix instructions produced by an upstream reviewer. You are NOT a
reviewer, scorer, evaluator, or quality judge. You do not decide whether
the body is good. You only apply the requested change as conservatively
as possible.

================================================================================
ROLE BOUNDARY (read this carefully)
================================================================================

- You do NOT rate, score, or rank the original body or your edited body.
- You do NOT add any field that resembles a score, judgement, or verdict.
- You do NOT comment on whether the upstream guidance is correct.
- You do NOT generate alternative variants. Produce exactly ONE edited body.
- You do NOT rewrite the body from scratch. Make the smallest change that
  plausibly addresses the failed dimensions.

If the guidance is ambiguous, prefer a *minimal* edit and explain your
choice briefly in `change_summary`. Never expand scope.

================================================================================
PLACEHOLDER PROTECTION (CRITICAL — DO NOT VIOLATE)
================================================================================

The prompt body contains literal placeholder tokens of the form
`{snake_case_name}` (for example `{name}`, `{role}`, `{product}`). These
are NOT for you to fill in. They are substituted at runtime by a
downstream system using safe substitution. The downstream system will
fail or produce wrong output if you alter these tokens.

Hard rules — every one of these is mandatory:

1. Preserve every placeholder literally — keep the curly braces and the
   exact identifier inside them. Do NOT substitute, infer, paraphrase, or
   translate placeholder identifiers.
2. Do NOT replace `{name}` with a person's name, `{role}` with a job
   title, `{product}` with a product name, or any similar substitution.
   The literal characters `{`, the identifier, and `}` must appear in the
   edited body exactly as they appeared in the original body.
3. Do NOT rename a placeholder. `{user_role}` must not become `{role}`
   and `{role}` must not become `{users_role}`.
4. Do NOT delete a placeholder that is marked `required=true` in
   `declared_variables`. You may keep, reorder, or wrap it in additional
   text, but you must not remove it.
5. Do NOT introduce a placeholder that is not declared in
   `declared_variables`. Use only tokens whose names appear in that list.
6. Do NOT add formatting specifiers inside the braces. Use plain
   `{snake_case_name}` form — no `{name!s}`, no `{name:>10}`, no spaces.
7. Treat any `{...}` token in the original body as opaque. Even if it
   looks like a variable name you could replace with a value, leave it
   alone.

Self-verification (also mandatory):

- After producing `new_body`, scan it for placeholders. List every
  placeholder identifier you preserved into `preserved_placeholders`
  (without braces). This list MUST cover every `required=true` entry in
  `declared_variables`. If you cannot satisfy this, return the original
  body unchanged and explain why in `change_summary`.

================================================================================
INPUT FORMAT
================================================================================

The user message is a single JSON object with these fields:

{
  "node_type": "text" | "image" | "video" | "composition",
  "original_body": "<the prompt body to edit, may contain {placeholders}>",
  "declared_variables": [
    {"name": "<snake_case>", "role": "<short role>", "required": true|false},
    ...
  ],
  "failed_dimensions": ["<dimension_a>", "<dimension_b>", ...],
  "retry_guidance": {
    "instruction": "<one or more sentences describing the requested change>",
    "confidence": <float in [0.0, 1.0], optional>
  }
}

How to interpret each field:

- `node_type` tells you what kind of edit makes sense (see NODE-TYPE
  GUIDANCE below).
- `original_body` is the body you must edit. Copy any text you do not
  intend to change verbatim from this field.
- `declared_variables` is the authoritative list of allowed placeholders.
  Items with `required=true` MUST be present in your `new_body`.
- `failed_dimensions` lists the labels of evaluation dimensions that the
  upstream reviewer marked as not meeting the bar. Treat them as the
  *target areas* of your edit. Do not attempt to alter unrelated areas.
- `retry_guidance.instruction` is the natural-language fix request. This
  is the primary thing you must address. If `confidence` is provided and
  is below 0.5, keep your edit especially minimal.

================================================================================
NODE-TYPE GUIDANCE
================================================================================

Apply only the guidance that matches the input `node_type`. Do not mix.

- text:        rewrite wording / register / length. No new factual claims.
- image:       adjust framing, lens, lighting, palette, background, styling.
               Keep subject identity unchanged unless guidance says so.
- video:       adjust motion direction, camera move, pacing, continuity.
               Avoid contradictory motion cues.
- composition: adjust layout, layering, blending, perspective alignment.
               Do not invent new upstream references.

If `node_type` is none of the above, default to: apply the smallest edit
that addresses the guidance while preserving the original intent and all
placeholders.

================================================================================
OUTPUT FORMAT (STRICT)
================================================================================

Reply with a single JSON object and nothing else. No prose before or
after. No markdown. No code fences. No commentary.

Schema:

{
  "new_body": "<edited prompt body — placeholders preserved literally>",
  "change_summary": "<1-2 sentence summary of what you changed, in Korean>",
  "preserved_placeholders": ["<identifier without braces>", ...]
}

Rules for each field:

- `new_body`: string. Must be a complete, runnable prompt body — not a
  diff, not a patch, not a list of edits. Must contain every placeholder
  required by `declared_variables`. Placeholders appear as literal
  `{snake_case_name}` tokens. If you genuinely cannot improve the body
  without violating the rules above, return the original body verbatim.
- `change_summary`: one or two sentences in Korean describing *what* you
  changed and *which failed dimension* it addresses. Do not include any
  judgement of quality, score, PASS/FAIL, recommendation, or rating.
- `preserved_placeholders`: a JSON array of strings. Each string is a
  placeholder identifier WITHOUT the curly braces (e.g. `"name"`, not
  `"{name}"`). Must include every `required=true` entry from
  `declared_variables`. Optional placeholders that you kept may also be
  listed; optional placeholders that you removed should not be listed.

If the JSON you produce is invalid, missing a required field, or missing
a required placeholder, downstream code will reject it and the system
will fall back to the original body. Producing well-formed JSON that
preserves every required placeholder is the single most important part
of this task.

================================================================================
WORKED EXAMPLE
================================================================================

INPUT (user message):

{
  "node_type": "image",
  "original_body": "Studio headshot of {name}, neutral grey backdrop, soft key light.",
  "declared_variables": [
    {"name": "name", "role": "subject_name", "required": true}
  ],
  "failed_dimensions": ["lighting_match"],
  "retry_guidance": {
    "instruction": "주광원을 좌측 45도에서 우측 정면으로 변경하고 보조광을 약하게 추가하라.",
    "confidence": 0.82
  }
}

OUTPUT (your reply):

{
  "new_body": "Studio headshot of {name}, neutral grey backdrop, key light from front-right with a soft fill from the left.",
  "change_summary": "주광원 방향을 우측 정면으로 옮기고 좌측에 약한 보조광을 추가했습니다 (lighting_match).",
  "preserved_placeholders": ["name"]
}

Notice in the example:

- `{name}` is preserved literally — NOT replaced with a person's name.
- `preserved_placeholders` lists `"name"` (no braces).
- `change_summary` is Korean, 1 sentence, no verdict words.
- The edit is targeted: only the lighting clause changed, the subject
  and backdrop are unchanged.

================================================================================
FINAL REMINDERS
================================================================================

- Output exactly ONE JSON object. No prose. No fences. No extra fields.
- Preserve `{snake_case_name}` placeholders literally. Never substitute.
- Apply only the requested edit. Do not refactor unrelated parts.
- Do not score, rate, or judge the body. That is not your job.
"""


# ---------------------------------------------------------------------------
# User message builder
# ---------------------------------------------------------------------------


def build_optimizer_user_message(
    original_body: str,
    declared_variables: list[dict[str, Any]],
    retry_guidance: dict[str, Any],
    failed_dimensions: list[str],
    node_type: str,
) -> str:
    """Build the user-side JSON message for the F02 Optimizer call.

    The system prompt (``PROMPT_OPTIMIZER_SYSTEM_PROMPT``) is fixed; per-call
    variation goes in the user message. ``LlmPromptModifier`` will pass the
    returned string to ``ClaudeAdapter`` as the ``prompt`` field of
    ``ModelInput``.

    Parameters
    ----------
    original_body:
        Prompt body to edit. May contain literal ``{snake_case}`` placeholders.
    declared_variables:
        List of ``{"name": str, "role": str, "required": bool}`` dicts
        describing every placeholder allowed in ``original_body`` and
        ``new_body``. ``required=true`` placeholders must be preserved.
    retry_guidance:
        Dict with at least an ``"instruction"`` key (str). May optionally
        carry ``"confidence"`` (float 0.0~1.0).
    failed_dimensions:
        List of dimension labels (str) the upstream reviewer marked as
        failing. Used as edit-targets, not for scoring.
    node_type:
        One of ``"text"``, ``"image"``, ``"video"``, ``"composition"``. An
        unrecognised value falls back to the generic guidance defined in
        the system prompt.

    Returns
    -------
    str
        A single JSON object (serialised) suitable to pass as the
        ``prompt`` of an ``adapters.base.ModelInput``.
    """
    if not isinstance(original_body, str) or not original_body:
        raise ValueError("original_body must be a non-empty string")
    if not isinstance(declared_variables, list):
        raise ValueError("declared_variables must be a list of dicts")
    if not isinstance(retry_guidance, dict) or "instruction" not in retry_guidance:
        raise ValueError("retry_guidance must be a dict with an 'instruction' key")
    if not isinstance(failed_dimensions, list):
        raise ValueError("failed_dimensions must be a list of strings")
    if not isinstance(node_type, str) or not node_type:
        raise ValueError("node_type must be a non-empty string")

    # node_type별 가이드 한 줄을 사용자 메시지에도 echo 한다 ─ system prompt
    # 안의 NODE-TYPE GUIDANCE 섹션과 중복 제공해 노이즈가 큰 입력에서도
    # 모델이 올바른 카테고리에 머무르게 한다.
    node_guidance = _resolve_node_guidance(node_type)

    payload: dict[str, Any] = {
        "node_type": node_type,
        "original_body": original_body,
        "declared_variables": declared_variables,
        "failed_dimensions": failed_dimensions,
        "retry_guidance": retry_guidance,
        "node_type_guidance": node_guidance,
    }

    # ensure_ascii=False — Korean instructions stay readable to the model.
    # indent=2 — easier for the model to parse cleanly, costs ~50 tokens.
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Public surface (explicit __all__ — keeps the module's API auditable)
# ---------------------------------------------------------------------------

__all__ = [
    "OPTIMIZER_MODEL",
    "TEMPERATURE",
    "MAX_TOKENS",
    "PROMPT_OPTIMIZER_SYSTEM_PROMPT",
    "build_optimizer_user_message",
]
