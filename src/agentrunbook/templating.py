from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


class TemplateError(KeyError):
    """Raised when a template references a missing value."""


TOKEN_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*}}")


def render_template(template: str, context: Mapping[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = resolve_path(context, key)
        return str(value)

    return TOKEN_PATTERN.sub(replace, template)


def resolve_path(context: Mapping[str, Any], path: str) -> Any:
    value: Any = context
    for part in path.split("."):
        if isinstance(value, Mapping) and part in value:
            value = value[part]
            continue
        raise TemplateError(f"missing template value: {path}")
    return value
