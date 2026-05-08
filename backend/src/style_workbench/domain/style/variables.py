from __future__ import annotations

import re

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def extract_variables(template: str) -> list[str]:
    """Return unique placeholder names found in template, preserving first-seen order."""
    seen: dict[str, None] = {}
    for m in _PLACEHOLDER_RE.finditer(template):
        seen[m.group(1)] = None
    return list(seen)


def validate_variables(template: str, provided: set[str]) -> list[str]:
    """Return list of placeholder names referenced in template but absent from provided."""
    return [v for v in extract_variables(template) if v not in provided]
