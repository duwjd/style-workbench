from __future__ import annotations

from abc import ABC, abstractmethod

from style_workbench.adapters.base import ModelInput, ModelOutput
from style_workbench.adapters.registry import get_adapter
from style_workbench.domain.style.entity import Node, NodeType


class NodeRunner(ABC):
    @abstractmethod
    async def run(self, node: Node, resolved_prompt: str) -> ModelOutput: ...

    @classmethod
    def for_type(cls, node_type: NodeType) -> NodeRunner:
        from style_workbench.engine.node_runners.composition_node import CompositionNodeRunner
        from style_workbench.engine.node_runners.image_node import ImageNodeRunner
        from style_workbench.engine.node_runners.text_node import TextNodeRunner
        from style_workbench.engine.node_runners.video_node import VideoNodeRunner

        runners: dict[NodeType, NodeRunner] = {
            NodeType.TEXT_GENERATION: TextNodeRunner(),
            NodeType.IMAGE_GENERATION: ImageNodeRunner(),
            NodeType.VIDEO_GENERATION: VideoNodeRunner(),
            NodeType.COMPOSITION: CompositionNodeRunner(),
        }
        return runners[node_type]


async def _call_adapter(node: Node, resolved_prompt: str) -> ModelOutput:
    adapter = get_adapter(node.model.provider)
    return await adapter.generate(ModelInput(model_id=node.model.model_id, prompt=resolved_prompt))
