from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from style_workbench.adapters.base import ModelInput, ModelOutput
from style_workbench.adapters.base import ModelAdapter
from style_workbench.adapters.registry import clear_registry, register
from style_workbench.core.ids import new_ulid
from style_workbench.domain.style.entity import DAG, Edge, ModelRef, Node, NodeInput, NodeType
from style_workbench.engine.executor import DagExecutor
from style_workbench.infra.db.models.run import NodeExecution, Run
from style_workbench.infra.db.models.style import Style, StyleVersion


# ── Stub adapters ──────────────────────────────────────────────────────────────

class _StubTextAdapter(ModelAdapter):
    async def generate(self, input: ModelInput) -> ModelOutput:
        return ModelOutput(text="generated caption", input_tokens=5, output_tokens=3, cost_usd=0.0001)

    def cost_estimate(self, model_id: str, input: ModelInput) -> float:
        return 0.0


class _StubImageAdapter(ModelAdapter):
    async def generate(self, input: ModelInput) -> ModelOutput:
        return ModelOutput(
            text="",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.003,
            artifact_url="https://example.com/image.jpg",
        )

    def cost_estimate(self, model_id: str, input: ModelInput) -> float:
        return 0.0


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def stub_registry() -> None:
    register("stub_text", _StubTextAdapter())
    register("stub_image", _StubImageAdapter())
    yield  # type: ignore[misc]
    clear_registry()


@pytest.fixture
async def run_id(session: AsyncSession) -> str:
    style = Style(id=new_ulid(), name="Test", status="draft", current_version=1)
    session.add(style)
    await session.flush()

    sv = StyleVersion(id=new_ulid(), style_id=style.id, version=1, dag={})
    session.add(sv)
    await session.flush()

    run = Run(style_version_id=sv.id, status="running", user_input={"concept": "beach"})
    session.add(run)
    await session.flush()

    return run.id


# ── Tests ──────────────────────────────────────────────────────────────────────

async def test_executor_2_node_dag(session: AsyncSession, run_id: str) -> None:
    dag = DAG(
        nodes=[
            Node(
                id="n1",
                type=NodeType.TEXT_GENERATION,
                model=ModelRef(provider="stub_text", model_id="stub"),
                prompt_template="Write a caption for {concept}",
            ),
            Node(
                id="n2",
                type=NodeType.IMAGE_GENERATION,
                model=ModelRef(provider="stub_image", model_id="stub"),
                prompt_template="Generate image: {caption}",
                inputs=[NodeInput(source="node_output:n1", role="caption")],
            ),
        ],
        edges=[Edge(source="n1", target="n2")],
        variables=["concept"],
    )

    executor = DagExecutor(session=session)
    result = await executor.execute(dag, {"concept": "beach"}, run_id)

    # Output assertions
    assert result.outputs["n1"].text == "generated caption"
    assert result.outputs["n2"].artifact_url == "https://example.com/image.jpg"

    # DB persistence assertions
    rows = list(await session.scalars(select(NodeExecution).where(NodeExecution.run_id == run_id)))
    assert len(rows) == 2
    by_node = {ne.node_id: ne for ne in rows}

    assert by_node["n1"].node_type == "text_generation"
    assert by_node["n1"].model_provider == "stub_text"
    assert by_node["n1"].status == "succeeded"

    assert by_node["n2"].node_type == "image_generation"
    assert by_node["n2"].artifact_url == "https://example.com/image.jpg"
    assert by_node["n2"].status == "succeeded"

    # n2's resolved prompt should include n1's output
    assert "generated caption" in (by_node["n2"].prompt_resolved or "")
