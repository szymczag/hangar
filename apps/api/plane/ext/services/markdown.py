# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Markdown accepted on write surfaces, rendered to the HTML the editor stores.

A caller that files work items from a script writes markdown, not editor HTML.
Rendering happens here and the result is handed to the same
`validate_html_content` (nh3) pass that hand-written HTML goes through, so there
is one sanitizer for both, not two policies to keep in step.
"""

import mistune
from rest_framework import serializers

# Descriptions are prose. The 10MB ceiling in content_validator is sized for a
# pasted document; markdown that large is a mistake worth reporting as one.
MAX_MARKDOWN_SIZE = 1024 * 1024

EMPTY_DOCUMENT = "<p></p>"

# escape=True is mistune's default and is stated anyway: it is the setting that
# keeps raw HTML written inside markdown from reaching the document as markup.
# The nh3 pass afterwards is the second line, not the only one.
_render = mistune.create_markdown(escape=True, plugins=["strikethrough", "table", "task_lists", "url"])


def render_markdown(markdown_content: str) -> str:
    """Render markdown to HTML, or raise ValidationError for input we refuse."""

    if markdown_content is None:
        return EMPTY_DOCUMENT
    if not isinstance(markdown_content, str):
        raise serializers.ValidationError("Markdown content must be text")
    if len(markdown_content.encode("utf-8")) > MAX_MARKDOWN_SIZE:
        raise serializers.ValidationError(
            f"Markdown content exceeds maximum size limit ({MAX_MARKDOWN_SIZE // 1024}KB)"
        )
    if not markdown_content.strip():
        return EMPTY_DOCUMENT

    return _render(markdown_content) or EMPTY_DOCUMENT


def resolve_markdown_input(data: dict, *, html_field: str, markdown_field: str) -> dict:
    """Move a markdown field onto its HTML field, before the HTML is sanitized.

    Both fields at once is an error rather than a silent preference: a caller
    that sends both has one of them wrong, and picking either hides which.
    """

    if markdown_field not in data:
        return data

    markdown_content = data.pop(markdown_field)
    if data.get(html_field) not in (None, ""):
        raise serializers.ValidationError({markdown_field: f"Send either {markdown_field} or {html_field}, not both"})

    data[html_field] = render_markdown(markdown_content)
    return data
