"""Prompt templates. Each .j2 file defines a `system` and a `user` block."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
    keep_trailing_newline=False,
)


def render(name: str, **context) -> tuple[str, str]:
    """Render `<name>.j2` and return (system, user) prompt strings."""
    tmpl = _env.get_template(f"{name}.j2")
    ctx = tmpl.new_context(context)
    system = "".join(tmpl.blocks["system"](ctx)).strip()
    user = "".join(tmpl.blocks["user"](ctx)).strip()
    return system, user
