from __future__ import annotations

from enum import StrEnum

from style_workbench.domain.style.entity import NodeType


class ImageDimension(StrEnum):
    TEXT_ABSENCE = "text_absence"
    RESOLUTION_QUALITY = "resolution_quality"
    COMPOSITION = "composition"
    FACE_NATURAL = "face_natural"
    SKIN_TONE = "skin_tone"
    IDENTITY_MATCH = "identity_match"
    SCALE_NATURAL = "scale_natural"
    LIGHTING_MATCH = "lighting_match"
    SHADOW_CONSISTENT = "shadow_consistent"
    SEAM_CLEAN = "seam_clean"
    OBJECT_PRESERVED = "object_preserved"
    EFFECT_PHYSICS = "effect_physics"
    EFFECT_INTENSITY = "effect_intensity"
    COLOR_TONE = "color_tone"


class VideoDimension(StrEnum):
    MOTION_ARTIFACT = "motion_artifact"
    SUBJECT_PRESERVATION = "subject_preservation"
    MOTION_COMPLIANCE = "motion_compliance"
    SPEED_CONSISTENCY = "speed_consistency"
    FACE_CONSISTENCY = "face_consistency"
    COMPOSITE_SEAM = "composite_seam"
    OBJECT_STABILITY = "object_stability"
    EFFECT_CONTINUITY = "effect_continuity"


class TextDimension(StrEnum):
    TONE_MATCH = "tone_match"
    LENGTH = "length"
    FORBIDDEN_WORDS = "forbidden_words"


class CompositionDimension(StrEnum):
    CONSISTENCY = "consistency"
    AESTHETIC_BALANCE = "aesthetic_balance"
    BRIEF_MATCH = "brief_match"


# Python 내부에서만 판정에 사용. LLM에 전달하지 않는다.
PASS_THRESHOLD: float = 0.7

# 노드 타입별 기본 평가 차원 (공통 차원만 — 고급 차원은 서비스에서 추가 가능)
_BASE_DIMENSIONS: dict[NodeType, frozenset[str]] = {
    NodeType.IMAGE_GENERATION: frozenset(
        {
            ImageDimension.TEXT_ABSENCE,
            ImageDimension.RESOLUTION_QUALITY,
            ImageDimension.COMPOSITION,
        }
    ),
    NodeType.VIDEO_GENERATION: frozenset(
        {
            VideoDimension.MOTION_ARTIFACT,
            VideoDimension.SUBJECT_PRESERVATION,
            VideoDimension.MOTION_COMPLIANCE,
            VideoDimension.SPEED_CONSISTENCY,
        }
    ),
    NodeType.TEXT_GENERATION: frozenset(
        {
            TextDimension.TONE_MATCH,
            TextDimension.LENGTH,
            TextDimension.FORBIDDEN_WORDS,
        }
    ),
    NodeType.COMPOSITION: frozenset(
        {
            CompositionDimension.CONSISTENCY,
            CompositionDimension.AESTHETIC_BALANCE,
            CompositionDimension.BRIEF_MATCH,
        }
    ),
}


def dimensions_for(node_type: NodeType) -> frozenset[str]:
    """노드 타입에 대응하는 기본 평가 차원 집합을 반환한다."""
    return _BASE_DIMENSIONS.get(node_type, frozenset())
