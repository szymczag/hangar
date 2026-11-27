# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The editor menus page the visual seed writes, and the image it uploads.

The editor menu stories open this page and find each node by the text the
manifest publishes, so the page must carry every node they act on. The image
is generated, not committed; the baselines that show it depend on its bytes
never changing.
"""

import struct
import uuid
import zlib
from html.parser import HTMLParser

import pytest

from plane.ext.management.commands.seed_visual_fixtures import (
    EDITOR_MENUS_IMAGE_ID,
    Command,
    editor_menus_html,
    editor_menus_png,
)


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


@pytest.mark.unit
def test_the_page_carries_every_node_the_menu_stories_act_on():
    user_id = uuid.UUID("a0000000-0000-4000-8000-000000000093")
    html = editor_menus_html(user_id)
    parser = _Tags()
    parser.feed(html)
    tags = {tag for tag, _ in parser.tags}

    assert {"table", "th", "td", "pre", "code", "a", "mention-component", "image-component"} <= tags
    attrs = {tag: attributes for tag, attributes in parser.tags}
    assert attrs["a"]["href"] == Command.EDITOR_MENUS_TEXT["linkHref"]
    assert attrs["mention-component"]["entity_identifier"] == str(user_id)
    assert attrs["mention-component"]["entity_name"] == "user_mention"
    assert attrs["image-component"]["src"] == str(EDITOR_MENUS_IMAGE_ID)
    assert attrs["image-component"]["status"] == "uploaded"
    assert any(tag == "span" and attributes.get("data-type") == "emoji" for tag, attributes in parser.tags)
    assert any(
        tag == "div" and attributes.get("data-block-type") == "callout-component" for tag, attributes in parser.tags
    )
    for key in ("selection", "link", "code", "callout", "lastParagraph"):
        assert Command.EDITOR_MENUS_TEXT[key] in html


@pytest.mark.unit
def test_the_image_is_a_valid_fixed_png():
    image = editor_menus_png()

    assert image == editor_menus_png()
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    length, kind = struct.unpack(">I4s", image[8:16])
    assert kind == b"IHDR" and length == 13
    width, height, depth, colour, _, _, _ = struct.unpack(">IIBBBBB", image[16:29])
    assert (width, height, depth, colour) == (320, 160, 8, 2)

    # Walk the chunks, checking each CRC, and decompress the pixel data.
    offset, data = 8, b""
    while offset < len(image):
        (size,) = struct.unpack(">I", image[offset : offset + 4])
        kind = image[offset + 4 : offset + 8]
        body = image[offset + 8 : offset + 8 + size]
        (crc,) = struct.unpack(">I", image[offset + 8 + size : offset + 12 + size])
        assert crc == zlib.crc32(kind + body) & 0xFFFFFFFF
        if kind == b"IDAT":
            data += body
        offset += 12 + size
    assert kind == b"IEND"
    assert len(zlib.decompress(data)) == height * (1 + width * 3)
