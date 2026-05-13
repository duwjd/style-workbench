from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from style_workbench.domain.style.schema import style_from_dict
from style_workbench.domain.style.validation import validate_dag
from style_workbench.domain.style.variables import extract_variables

_FIXTURE_DIR = Path(__file__).parent
_FIXTURE_PATH = _FIXTURE_DIR / "fixture_variants.json"


# ---------------------------------------------------------------------------
# Internal Pydantic schema — mirrors the expected JSON structure
# ---------------------------------------------------------------------------


class _NodeInputSchema(BaseModel):
    source: str
    role: str


class _ModelRefSchema(BaseModel):
    provider: str
    model_id: str


class _NodeSchema(BaseModel):
    id: str
    type: str
    model: _ModelRefSchema
    prompt_template: str
    inputs: list[_NodeInputSchema] = []


class _DagSchema(BaseModel):
    nodes: list[_NodeSchema]
    edges: list[dict[str, str]]
    variables: list[str]


class _VariantSchema(BaseModel):
    name: str
    tags: list[str]
    dag: _DagSchema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_fixture() -> list[dict[str, Any]]:
    raw: list[dict[str, Any]] = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    return raw


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fixture_schema_valid() -> None:
    """All 5 fixture variants satisfy the expected _VariantSchema structure."""
    fixture = _load_fixture()
    assert len(fixture) == 5, f"Expected 5 variants, got {len(fixture)}"
    for d in fixture:
        _VariantSchema.model_validate(d)


def test_fixture_dag_no_cycles() -> None:
    """Each fixture variant's DAG is acyclic (validate_dag must not raise)."""
    fixture = _load_fixture()
    for d in fixture:
        style = style_from_dict(d, concept="비즈니스 포트레이트", vertical="portrait")
        validate_dag(style.dag)


def test_fixture_variables_consistent() -> None:
    """Every {placeholder} in a node's prompt_template is declared in dag.variables.

    Upstream node outputs are wired via inputs[].source = "node_output:<id>",
    not via template braces. So inputs[].role for node_output sources are
    intentionally excluded from the declared-variables check.
    """
    fixture = _load_fixture()
    for variant in fixture:
        dag: dict[str, Any] = variant["dag"]
        declared: set[str] = set(dag["variables"])
        nodes: list[dict[str, Any]] = dag["nodes"]
        for node in nodes:
            used = set(extract_variables(str(node["prompt_template"])))
            # Roles that come from user_input are also declared variables.
            # Roles from node_output sources are NOT template placeholders —
            # they are delivered via the inputs wire, not via brace substitution.
            unresolved = used - declared
            assert unresolved == set(), (
                f"Variant '{variant['name']}', node '{node['id']}': "
                f"unresolved placeholders {unresolved} not in dag.variables {declared}"
            )
