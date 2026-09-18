from __future__ import annotations

import bleach
from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark", {"html": False, "linkify": True, "breaks": True})
_ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {
    "p", "pre", "code", "blockquote", "hr", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "input", "del", "table", "thead", "tbody", "tr", "th", "td"
}
_ALLOWED_ATTRS = {"a": ["href", "title", "rel"], "input": ["type", "checked", "disabled"], "*": ["class"]}


def render_markdown(text: str) -> str:
    # Pre-render GitHub-ish checkboxes without allowing arbitrary HTML.
    lines = []
    for line in (text or "").splitlines():
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        if stripped.startswith("- [ ] "):
            line = indent + "- <input type=\"checkbox\" disabled> " + stripped[6:]
        elif stripped.lower().startswith("- [x] "):
            line = indent + "- <input type=\"checkbox\" checked disabled> " + stripped[6:]
        lines.append(line)
    # MarkdownIt html=False escapes the generated input, so temporarily allow only our sentinel.
    sentinel = "\n".join(lines).replace('<input type="checkbox" disabled>', 'CHECKBOX_UNCHECKED_SENTINEL').replace('<input type="checkbox" checked disabled>', 'CHECKBOX_CHECKED_SENTINEL')
    html = _md.render(sentinel)
    html = html.replace("CHECKBOX_UNCHECKED_SENTINEL", '<input type="checkbox" disabled>').replace("CHECKBOX_CHECKED_SENTINEL", '<input type="checkbox" checked disabled>')
    return bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, protocols={"http", "https", "mailto"}, strip=True)
