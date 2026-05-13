"""50-scenario golden fixture definitions for the F01 Auto Evaluation Loop.

Each GoldenScenario describes one node execution's retry lifecycle.

pass_at_attempt meaning:
  0  = PASS on the first (original) execution — no retry needed.
  1  = FAIL at attempt 0, PASS at attempt 1 (first retry).
  2  = FAIL at attempts 0,1, PASS at attempt 2 (second retry).
  3  = FAIL at attempts 0,1,2, PASS at attempt 3 (third retry).
  None = FAIL at all attempts 0,1,2,3 — max_retry exhausted, abort.

Scenario distribution (must satisfy AC-1 ≥60%):
  pass_at_attempt == 0:    20 scenarios  (40.0%)
  pass_at_attempt == 1:    12 scenarios  (24.0%)
  pass_at_attempt == 2:     5 scenarios  (10.0%)
  pass_at_attempt == 3:     3 scenarios   (6.0%)
  pass_at_attempt == None: 10 scenarios  (20.0%)
  ─────────────────────────────────────────────
  Total:                   50 scenarios (100.0%)
  PASS within 3 retries:  40 scenarios  (80.0%)  ← AC-1 threshold = 60%

Node-type distribution (≥10 per type):
  text:        15 scenarios
  image:       15 scenarios
  video:       10 scenarios
  composition: 10 scenarios

FAIL dimension coverage (≥5 distinct dimensions):
  text:        tone_match, length, forbidden_words
  image:       composition, lighting_match, face_natural, text_absence,
               resolution_quality, skin_tone, identity_match
  video:       motion_artifact, subject_preservation, motion_compliance,
               speed_consistency, face_consistency
  composition: consistency, aesthetic_balance, brief_match

Design principle:
  - F02 is absent → NoopPromptModifier is used → same prompt on retry.
  - Retry PASS scenarios model situations where the *orchestration mechanics*
    are correct (attempt tracking, repo writes, event emission, budget guard)
    rather than actual LLM improvement.
  - The mock evaluator drives PASS/FAIL deterministically per scenario.
  - No real LLM calls occur anywhere in this test suite.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoldenScenario:
    """Single node execution scenario for the golden pass-rate test.

    Attributes:
        name:              Human-readable unique identifier.
        node_type:         One of "text", "image", "video", "composition".
        pass_at_attempt:   Attempt number (0-3) at which the mock evaluator
                           returns PASS, or None if all attempts FAIL.
        failed_dimensions: Dimension names returned by the mock evaluator on
                           each FAIL attempt.  Same list repeated for all
                           FAIL attempts (NoopPromptModifier — no change).
        cost_per_attempt:  Simulated cost in KRW per execution attempt.
    """

    name: str
    node_type: str
    pass_at_attempt: int | None
    failed_dimensions: list[str] = field(default_factory=list)
    cost_per_attempt: float = 50.0  # conservative default (₩50 per attempt)


# ---------------------------------------------------------------------------
# TEXT scenarios — 15 total
# ---------------------------------------------------------------------------
# attempt 0 PASS: 6 scenarios
# attempt 1 PASS: 4 scenarios
# attempt 2 PASS: 2 scenarios
# attempt 3 PASS: 1 scenario
# FAIL all:       2 scenarios

_TEXT_SCENARIOS: list[GoldenScenario] = [
    # ── attempt 0 PASS (6) ───────────────────────────────────────────────
    GoldenScenario(
        name="text_biz_intro_tone_pass_a0",
        node_type="text",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=30.0,
    ),
    GoldenScenario(
        name="text_product_desc_length_pass_a0",
        node_type="text",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=30.0,
    ),
    GoldenScenario(
        name="text_caption_formal_pass_a0",
        node_type="text",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=30.0,
    ),
    GoldenScenario(
        name="text_slogan_concise_pass_a0",
        node_type="text",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=25.0,
    ),
    GoldenScenario(
        name="text_alt_text_neutral_pass_a0",
        node_type="text",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=20.0,
    ),
    GoldenScenario(
        name="text_hashtags_relevant_pass_a0",
        node_type="text",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=15.0,
    ),
    # ── attempt 1 PASS (4) ───────────────────────────────────────────────
    GoldenScenario(
        name="text_tone_mismatch_retry1_pass",
        node_type="text",
        pass_at_attempt=1,
        failed_dimensions=["tone_match"],
        cost_per_attempt=30.0,
    ),
    GoldenScenario(
        name="text_length_overrun_retry1_pass",
        node_type="text",
        pass_at_attempt=1,
        failed_dimensions=["length"],
        cost_per_attempt=30.0,
    ),
    GoldenScenario(
        name="text_forbidden_word_retry1_pass",
        node_type="text",
        pass_at_attempt=1,
        failed_dimensions=["forbidden_words"],
        cost_per_attempt=30.0,
    ),
    GoldenScenario(
        name="text_tone_length_both_fail_retry1_pass",
        node_type="text",
        pass_at_attempt=1,
        failed_dimensions=["tone_match", "length"],
        cost_per_attempt=30.0,
    ),
    # ── attempt 2 PASS (2) ───────────────────────────────────────────────
    GoldenScenario(
        name="text_all_dims_fail_retry2_pass",
        node_type="text",
        pass_at_attempt=2,
        failed_dimensions=["tone_match", "length", "forbidden_words"],
        cost_per_attempt=30.0,
    ),
    GoldenScenario(
        name="text_tone_persistent_retry2_pass",
        node_type="text",
        pass_at_attempt=2,
        failed_dimensions=["tone_match"],
        cost_per_attempt=30.0,
    ),
    # ── attempt 3 PASS (1) ───────────────────────────────────────────────
    GoldenScenario(
        name="text_stubborn_forbidden_retry3_pass",
        node_type="text",
        pass_at_attempt=3,
        failed_dimensions=["forbidden_words"],
        cost_per_attempt=30.0,
    ),
    # ── FAIL all (2) ─────────────────────────────────────────────────────
    GoldenScenario(
        name="text_unrecoverable_tone_fail_all",
        node_type="text",
        pass_at_attempt=None,
        failed_dimensions=["tone_match"],
        cost_per_attempt=30.0,
    ),
    GoldenScenario(
        name="text_unrecoverable_all_dims_fail_all",
        node_type="text",
        pass_at_attempt=None,
        failed_dimensions=["tone_match", "length", "forbidden_words"],
        cost_per_attempt=30.0,
    ),
]

# ---------------------------------------------------------------------------
# IMAGE scenarios — 15 total
# ---------------------------------------------------------------------------
# attempt 0 PASS: 6 scenarios
# attempt 1 PASS: 4 scenarios
# attempt 2 PASS: 2 scenarios
# attempt 3 PASS: 1 scenario
# FAIL all:       2 scenarios

_IMAGE_SCENARIOS: list[GoldenScenario] = [
    # ── attempt 0 PASS (6) ───────────────────────────────────────────────
    GoldenScenario(
        name="image_portrait_clean_pass_a0",
        node_type="image",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=200.0,
    ),
    GoldenScenario(
        name="image_product_shot_pass_a0",
        node_type="image",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=180.0,
    ),
    GoldenScenario(
        name="image_background_landscape_pass_a0",
        node_type="image",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=150.0,
    ),
    GoldenScenario(
        name="image_flat_lay_pass_a0",
        node_type="image",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=160.0,
    ),
    GoldenScenario(
        name="image_lifestyle_scene_pass_a0",
        node_type="image",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=170.0,
    ),
    GoldenScenario(
        name="image_logo_mockup_pass_a0",
        node_type="image",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=140.0,
    ),
    # ── attempt 1 PASS (4) ───────────────────────────────────────────────
    GoldenScenario(
        name="image_text_in_frame_retry1_pass",
        node_type="image",
        pass_at_attempt=1,
        failed_dimensions=["text_absence"],
        cost_per_attempt=200.0,
    ),
    GoldenScenario(
        name="image_bad_composition_retry1_pass",
        node_type="image",
        pass_at_attempt=1,
        failed_dimensions=["composition"],
        cost_per_attempt=200.0,
    ),
    GoldenScenario(
        name="image_lighting_mismatch_retry1_pass",
        node_type="image",
        pass_at_attempt=1,
        failed_dimensions=["lighting_match"],
        cost_per_attempt=200.0,
    ),
    GoldenScenario(
        name="image_low_resolution_retry1_pass",
        node_type="image",
        pass_at_attempt=1,
        failed_dimensions=["resolution_quality"],
        cost_per_attempt=200.0,
    ),
    # ── attempt 2 PASS (2) ───────────────────────────────────────────────
    GoldenScenario(
        name="image_face_distortion_retry2_pass",
        node_type="image",
        pass_at_attempt=2,
        failed_dimensions=["face_natural"],
        cost_per_attempt=200.0,
    ),
    GoldenScenario(
        name="image_skin_tone_off_retry2_pass",
        node_type="image",
        pass_at_attempt=2,
        failed_dimensions=["skin_tone"],
        cost_per_attempt=200.0,
    ),
    # ── attempt 3 PASS (1) ───────────────────────────────────────────────
    GoldenScenario(
        name="image_identity_mismatch_retry3_pass",
        node_type="image",
        pass_at_attempt=3,
        failed_dimensions=["identity_match"],
        cost_per_attempt=200.0,
    ),
    # ── FAIL all (2) ─────────────────────────────────────────────────────
    GoldenScenario(
        name="image_persistent_text_artifact_fail_all",
        node_type="image",
        pass_at_attempt=None,
        failed_dimensions=["text_absence", "composition"],
        cost_per_attempt=200.0,
    ),
    GoldenScenario(
        name="image_uncanny_face_fail_all",
        node_type="image",
        pass_at_attempt=None,
        failed_dimensions=["face_natural", "skin_tone"],
        cost_per_attempt=200.0,
    ),
]

# ---------------------------------------------------------------------------
# VIDEO scenarios — 10 total
# ---------------------------------------------------------------------------
# attempt 0 PASS: 4 scenarios
# attempt 1 PASS: 2 scenarios
# attempt 2 PASS: 1 scenario
# attempt 3 PASS: 1 scenario
# FAIL all:       2 scenarios

_VIDEO_SCENARIOS: list[GoldenScenario] = [
    # ── attempt 0 PASS (4) ───────────────────────────────────────────────
    GoldenScenario(
        name="video_pan_left_smooth_pass_a0",
        node_type="video",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=2500.0,
    ),
    GoldenScenario(
        name="video_zoom_in_stable_pass_a0",
        node_type="video",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=2500.0,
    ),
    GoldenScenario(
        name="video_static_portrait_pass_a0",
        node_type="video",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=2000.0,
    ),
    GoldenScenario(
        name="video_dolly_forward_pass_a0",
        node_type="video",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=2500.0,
    ),
    # ── attempt 1 PASS (2) ───────────────────────────────────────────────
    GoldenScenario(
        name="video_flicker_artifact_retry1_pass",
        node_type="video",
        pass_at_attempt=1,
        failed_dimensions=["motion_artifact"],
        cost_per_attempt=2500.0,
    ),
    GoldenScenario(
        name="video_subject_morph_retry1_pass",
        node_type="video",
        pass_at_attempt=1,
        failed_dimensions=["subject_preservation"],
        cost_per_attempt=2500.0,
    ),
    # ── attempt 2 PASS (1) ───────────────────────────────────────────────
    GoldenScenario(
        name="video_wrong_motion_retry2_pass",
        node_type="video",
        pass_at_attempt=2,
        failed_dimensions=["motion_compliance"],
        cost_per_attempt=2500.0,
    ),
    # ── attempt 3 PASS (1) ───────────────────────────────────────────────
    GoldenScenario(
        name="video_speed_inconsistent_retry3_pass",
        node_type="video",
        pass_at_attempt=3,
        failed_dimensions=["speed_consistency"],
        cost_per_attempt=2500.0,
    ),
    # ── FAIL all (2) ─────────────────────────────────────────────────────
    GoldenScenario(
        name="video_face_morph_severe_fail_all",
        node_type="video",
        pass_at_attempt=None,
        failed_dimensions=["face_consistency", "motion_artifact"],
        cost_per_attempt=2500.0,
    ),
    GoldenScenario(
        name="video_unrecoverable_warp_fail_all",
        node_type="video",
        pass_at_attempt=None,
        failed_dimensions=["motion_artifact", "subject_preservation", "motion_compliance"],
        cost_per_attempt=2500.0,
    ),
]

# ---------------------------------------------------------------------------
# COMPOSITION scenarios — 10 total
# ---------------------------------------------------------------------------
# attempt 0 PASS: 4 scenarios
# attempt 1 PASS: 2 scenarios
# attempt 2 PASS: 0 scenarios  (balance to match totals)
# attempt 3 PASS: 0 scenarios
# FAIL all:       4 scenarios

_COMPOSITION_SCENARIOS: list[GoldenScenario] = [
    # ── attempt 0 PASS (4) ───────────────────────────────────────────────
    GoldenScenario(
        name="comp_portrait_product_pass_a0",
        node_type="composition",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=300.0,
    ),
    GoldenScenario(
        name="comp_lifestyle_banner_pass_a0",
        node_type="composition",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=280.0,
    ),
    GoldenScenario(
        name="comp_editorial_layout_pass_a0",
        node_type="composition",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=320.0,
    ),
    GoldenScenario(
        name="comp_background_swap_pass_a0",
        node_type="composition",
        pass_at_attempt=0,
        failed_dimensions=[],
        cost_per_attempt=250.0,
    ),
    # ── attempt 1 PASS (2) ───────────────────────────────────────────────
    GoldenScenario(
        name="comp_style_inconsistent_retry1_pass",
        node_type="composition",
        pass_at_attempt=1,
        failed_dimensions=["consistency"],
        cost_per_attempt=300.0,
    ),
    GoldenScenario(
        name="comp_visual_imbalance_retry1_pass",
        node_type="composition",
        pass_at_attempt=1,
        failed_dimensions=["aesthetic_balance"],
        cost_per_attempt=300.0,
    ),
    # ── FAIL all (4) ─────────────────────────────────────────────────────
    GoldenScenario(
        name="comp_brief_deviated_fail_all",
        node_type="composition",
        pass_at_attempt=None,
        failed_dimensions=["brief_match"],
        cost_per_attempt=300.0,
    ),
    GoldenScenario(
        name="comp_all_dims_fail_all",
        node_type="composition",
        pass_at_attempt=None,
        failed_dimensions=["consistency", "aesthetic_balance", "brief_match"],
        cost_per_attempt=300.0,
    ),
    GoldenScenario(
        name="comp_persistent_inconsistency_fail_all",
        node_type="composition",
        pass_at_attempt=None,
        failed_dimensions=["consistency"],
        cost_per_attempt=300.0,
    ),
    GoldenScenario(
        name="comp_brief_style_both_fail_all",
        node_type="composition",
        pass_at_attempt=None,
        failed_dimensions=["brief_match", "aesthetic_balance"],
        cost_per_attempt=300.0,
    ),
]

# ---------------------------------------------------------------------------
# Master list
# ---------------------------------------------------------------------------

GOLDEN_SCENARIOS: list[GoldenScenario] = (
    _TEXT_SCENARIOS + _IMAGE_SCENARIOS + _VIDEO_SCENARIOS + _COMPOSITION_SCENARIOS
)

assert len(GOLDEN_SCENARIOS) == 50, f"Expected 50 scenarios, got {len(GOLDEN_SCENARIOS)}"
