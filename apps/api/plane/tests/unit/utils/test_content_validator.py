# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Attribute values in rich text, not only attribute names.

nh3 decides which attributes may exist. The editor turns some of their values
into CSS, classes or request paths, so the values are checked as well.
"""

import json

import pytest

from plane.bgtasks.issue_activities_task import sanitize_rich_text_payload
from plane.utils.content_validator import (
    EDITOR_COLOR_KEYS,
    sanitize_color_key,
    sanitize_email_fragment,
    validate_html_content,
)

OVERLAY = "position:fixed;inset:0;z-index:99999;background:url(https://attacker.example/px)"
ASSET_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"


def clean(html):
    is_valid, _, sanitized = validate_html_content(html)
    assert is_valid
    return sanitized


@pytest.mark.unit
class TestInlineStyle:
    def test_style_attribute_is_removed_everywhere(self):
        for html in (
            f'<p style="{OVERLAY}">x</p>',
            f'<div style="{OVERLAY}">x</div>',
            f'<table><tr><td style="{OVERLAY}">x</td><th style="{OVERLAY}">x</th></tr></table>',
        ):
            assert "style" not in clean(html)


@pytest.mark.unit
class TestColourAttributes:
    @pytest.mark.parametrize(
        "html",
        [
            f'<span data-text-color="red;{OVERLAY}">x</span>',
            f'<span data-background-color="red;{OVERLAY}">x</span>',
            f'<table><tr><td background="red;{OVERLAY}">x</td></tr></table>',
            f'<table><tr><td textcolor="red;{OVERLAY}">x</td></tr></table>',
            f'<table><tr background="red;{OVERLAY}"><td>x</td></tr></table>',
            f'<div data-block-type="callout" data-background="red;{OVERLAY}">x</div>',
        ],
    )
    def test_value_outside_the_palette_is_dropped(self, html):
        sanitized = clean(html)
        assert "position" not in sanitized
        assert "attacker.example" not in sanitized

    def test_palette_keys_are_kept(self):
        sanitized = clean('<span data-text-color="gray" data-background-color="light-blue">x</span>')
        assert 'data-text-color="gray"' in sanitized
        assert 'data-background-color="light-blue"' in sanitized

    def test_legacy_css_variable_becomes_its_key(self):
        sanitized = clean('<table><tr><th background="var(--editor-colors-peach-background)">x</th></tr></table>')
        assert 'background="peach"' in sanitized

    def test_color_key_helper(self):
        assert sanitize_color_key("gray") == "gray"
        assert sanitize_color_key(" dark-blue ") == "dark-blue"
        assert sanitize_color_key("var(--editor-colors-purple-text)") == "purple"
        assert sanitize_color_key("var(--editor-colors-unknown-text)") is None
        assert sanitize_color_key("red") is None
        assert sanitize_color_key(None) is None
        assert "gray" in EDITOR_COLOR_KEYS


@pytest.mark.unit
class TestOtherAttributeValues:
    def test_text_align_only_from_the_enum(self):
        assert 'data-text-align="center"' in clean('<p data-text-align="center">x</p>')
        assert "data-text-align" not in clean('<p data-text-align="justify;color:red">x</p>')

    def test_id_must_be_a_uuid(self):
        assert "id=" not in clean('<div id="config">x</div>')
        assert f'id="{ASSET_ID}"' in clean(f'<image-component id="{ASSET_ID}"></image-component>')

    def test_only_editor_classes_survive(self):
        sanitized = clean('<p class="fixed inset-0 z-50 editor-paragraph-block">x</p>')
        assert 'class="editor-paragraph-block"' in sanitized
        assert "fixed" not in sanitized

    def test_image_component_src_cannot_become_an_api_path(self):
        assert "src" not in clean('<image-component src="../../../workspaces/x/projects/y"></image-component>')
        assert f'src="{ASSET_ID}"' in clean(f'<image-component src="{ASSET_ID}"></image-component>')
        assert 'src="https://cdn.example/a.png"' in clean(
            '<image-component src="https://cdn.example/a.png"></image-component>'
        )

    def test_only_checkbox_inputs(self):
        sanitized = clean('<input type="text"><input type="password"><input type="checkbox" checked>')
        assert 'type="text"' not in sanitized
        assert 'type="password"' not in sanitized
        assert 'type="checkbox"' in sanitized

    def test_link_target_is_forced(self):
        assert 'target="_blank"' in clean('<a href="https://example.com" target="_self">x</a>')

    def test_code_language_is_a_token(self):
        assert "language" not in clean('<pre><code language="js fixed inset-0">x</code></pre>')
        assert 'language="javascript"' in clean('<pre><code language="javascript">x</code></pre>')

    def test_callout_emoji_url_scheme(self):
        assert "data-emoji-url" not in clean('<div data-emoji-url="javascript:alert(1)">x</div>')


@pytest.mark.unit
class TestEmailFragment:
    def test_parser_differential_comment_is_removed(self):
        sanitized = sanitize_email_fragment("<p>x</p><!--><img src=x onerror=alert(1)>-->")
        assert "<img" not in sanitized
        assert "onerror" not in sanitized.replace("&lt;", "")

    def test_no_style_class_forms_or_images(self):
        sanitized = sanitize_email_fragment(
            f'<p class="x" style="{OVERLAY}">hi</p><input type="text"><img src="https://t.example/p">'
            '<a href="javascript:alert(1)">bad</a><a href="https://ok.example">ok</a>'
        )
        assert "style" not in sanitized
        assert "class" not in sanitized
        assert "<input" not in sanitized
        assert "<img" not in sanitized
        assert "javascript:" not in sanitized
        assert 'href="https://ok.example"' in sanitized


@pytest.mark.unit
class TestActivityPayload:
    def test_rich_text_keys_are_sanitized(self):
        payload = json.dumps(
            {
                "comment_html": '<p style="position:fixed">x</p><img src=x onerror=alert(1)>',
                "description_html": f'<span data-text-color="red;{OVERLAY}">y</span>',
                "name": "<b>unchanged</b>",
            }
        )
        data = json.loads(sanitize_rich_text_payload(payload))
        assert "style" not in data["comment_html"]
        assert "onerror" not in data["comment_html"]
        assert "position" not in data["description_html"]
        # Plain fields are left alone; they are escaped where rendered.
        assert data["name"] == "<b>unchanged</b>"

    def test_non_json_and_empty_payloads_pass_through(self):
        assert sanitize_rich_text_payload(None) is None
        assert sanitize_rich_text_payload("") == ""
        assert sanitize_rich_text_payload("not json") == "not json"
        assert sanitize_rich_text_payload("[1, 2]") == "[1, 2]"
