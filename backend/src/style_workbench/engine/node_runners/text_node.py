from __future__ import annotations

from style_workbench.adapters.base import ModelOutput
from style_workbench.domain.style.entity import Node
from style_workbench.engine.node_runners.base import NodeRunner, _call_adapter


class TextNodeRunner(NodeRunner):
    async def run(self, node: Node, resolved_prompt: str) -> ModelOutput:
        return await _call_adapter(node, resolved_prompt)
