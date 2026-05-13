from __future__ import annotations

import re
from collections.abc import Mapping

# Only matches strict word-identifier placeholders: {name}, {user_input}, etc.
# Deliberately excludes format specs ({name:>10}), attribute access ({a.__class__}),
# positional indices ({0}), and nested braces — none of those are matched.
PLACEHOLDER_PATTERN = re.compile(r"\{(\w+)\}")


class TemplateError(Exception):
    """Domain error raised when template substitution fails.

    Subclasses StyleWorkbenchError only if imported from core.errors; here we
    keep it a plain Exception so that domain/prompt/template.py remains free of
    any cross-layer imports (domain must not import core).  The exception is
    registered in core/errors.py and caught there for HTTP mapping.
    """


def extract_placeholders(template: str) -> set[str]:
    """Return the set of placeholder names found in *template*.

    Only strict ``{word}`` patterns are considered placeholders.  Strings like
    ``{0}``, ``{name:>10}`` or ``{a.b}`` are **not** matched and will be left
    untouched by :func:`safe_substitute`.

    Example::

        >>> extract_placeholders("Hello {name}, you are {age} years old.")
        {'name', 'age'}
    """
    return set(PLACEHOLDER_PATTERN.findall(template))


def safe_substitute(
    template: str,
    context: Mapping[str, object],
    *,
    allow_missing: bool = False,
) -> str:
    """Substitute ``{name}`` placeholders with values from *context*.

    Security guarantees vs. ``str.format_map``:

    * Only ``\\{(\\w+)\\}`` is matched — no format specs, no attribute traversal,
      no positional indices.  A user-supplied value containing ``{``/``}`` or
      ``:`` characters cannot trigger further substitution or attribute access.
    * Each matched placeholder is replaced with ``str(context[key])``.

    Args:
        template:      The template string.
        context:       Mapping of placeholder name → value.
        allow_missing: When ``True``, placeholders absent from *context* are
                       left unchanged in the output.  When ``False`` (default),
                       a :class:`TemplateError` is raised for any missing key.

    Returns:
        The substituted string.

    Raises:
        TemplateError: If *allow_missing* is ``False`` and a placeholder key is
                       not present in *context*.
    """

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            if allow_missing:
                return match.group(0)
            raise TemplateError(f"Missing placeholder value: {key!r}")
        return str(context[key])

    return PLACEHOLDER_PATTERN.sub(_replace, template)
