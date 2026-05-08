from __future__ import annotations

from style_workbench.engine.retry import MAX_RETRIES, RetryPolicy, RetryState


def test_should_retry_within_limit() -> None:
    for attempt in range(MAX_RETRIES):
        state = RetryState(node_id="n1", attempt=attempt)
        assert RetryPolicy.should_retry(state) is True


def test_should_not_retry_at_limit() -> None:
    state = RetryState(node_id="n1", attempt=MAX_RETRIES)
    assert RetryPolicy.should_retry(state) is False


def test_apply_modifiers_appends_suffix() -> None:
    prompt = "Original prompt"
    state = RetryState(node_id="n1", attempt=0)
    new_prompt, new_state = RetryPolicy.apply_modifiers(
        prompt, "Fix something", ["text_absence"], state
    )
    assert "Original prompt" in new_prompt
    assert "Fix something" in new_prompt
    assert new_state.attempt == 1
    assert new_state.node_id == "n1"


def test_apply_modifiers_no_guidance_uses_modifier_dict() -> None:
    prompt = "Original"
    state = RetryState(node_id="n1", attempt=0)
    new_prompt, _ = RetryPolicy.apply_modifiers(prompt, None, ["text_absence"], state)
    # RETRY_MODIFIERS["text_absence"]에 "NO text"와 "NO watermark" 양쪽이 포함됨
    assert "NO text" in new_prompt or "NO watermark" in new_prompt


def test_apply_modifiers_empty_dims_no_prompt_change() -> None:
    prompt = "Original"
    state = RetryState(node_id="n1", attempt=0)
    new_prompt, new_state = RetryPolicy.apply_modifiers(prompt, None, [], state)
    assert new_prompt == "Original"
    assert new_state.attempt == 1


def test_apply_modifiers_increments_attempt() -> None:
    state = RetryState(node_id="n2", attempt=1)
    _, new_state = RetryPolicy.apply_modifiers("prompt", None, [], state)
    assert new_state.attempt == 2


def test_apply_modifiers_preserves_node_id() -> None:
    state = RetryState(node_id="my_node", attempt=0)
    _, new_state = RetryPolicy.apply_modifiers("prompt", "guidance", ["composition"], state)
    assert new_state.node_id == "my_node"


def test_apply_modifiers_multiple_dims() -> None:
    state = RetryState(node_id="n1", attempt=0)
    new_prompt, _ = RetryPolicy.apply_modifiers(
        "Base", None, ["text_absence", "resolution_quality"], state
    )
    assert "NO text" in new_prompt or "NO watermark" in new_prompt
    assert "high resolution" in new_prompt


def test_apply_modifiers_unknown_dim_ignored() -> None:
    """사전에 없는 차원 이름은 modifier 없이 무시되어야 한다."""
    state = RetryState(node_id="n1", attempt=0)
    new_prompt, _ = RetryPolicy.apply_modifiers("Base", None, ["unknown_dim_xyz"], state)
    # unknown dim은 modifier가 없으므로 prompt 변경 없음
    assert new_prompt == "Base"
