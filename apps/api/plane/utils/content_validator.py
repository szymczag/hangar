# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import base64
import re
import nh3
from plane.utils.exception_logger import log_exception
from bs4 import BeautifulSoup
from collections import defaultdict
import logging

logger = logging.getLogger("plane.api")

# Maximum allowed size for binary data (10MB)
MAX_SIZE = 10 * 1024 * 1024

# Suspicious patterns for binary data content
SUSPICIOUS_BINARY_PATTERNS = [
    "<html",
    "<!doctype",
    "<script",
    "javascript:",
    "data:",
    "<iframe",
]


def validate_binary_data(data):
    """
    Validate that binary data appears to be a valid document format
    and doesn't contain malicious content.

    Args:
        data (bytes or str): The binary data to validate, or base64-encoded string

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not data:
        return True, None  # Empty is OK

    # Handle base64-encoded strings by decoding them first
    if isinstance(data, str):
        try:
            binary_data = base64.b64decode(data)
        except Exception:
            return False, "Invalid base64 encoding"
    else:
        binary_data = data

    # Size check - 10MB limit
    if len(binary_data) > MAX_SIZE:
        return False, "Binary data exceeds maximum size limit (10MB)"

    # Basic format validation
    if len(binary_data) < 4:
        return False, "Binary data too short to be valid document format"

    # Check for suspicious text patterns (HTML/JS)
    try:
        decoded_text = binary_data.decode("utf-8", errors="ignore")[:200]
        if any(pattern in decoded_text.lower() for pattern in SUSPICIOUS_BINARY_PATTERNS):
            return False, "Binary data contains suspicious content patterns"
    except Exception:
        pass  # Binary data might not be decodable as text, which is fine

    return True, None


# Combine custom components and editor-specific nodes into a single set of tags
CUSTOM_TAGS = {
    # editor node/tag names
    "mention-component",
    "label",
    "input",
    "image-component",
}
ALLOWED_TAGS = nh3.ALLOWED_TAGS | CUSTOM_TAGS

# Merge nh3 defaults with all attributes used across our custom components.
# There is no `style`: the editor renders colour and alignment as data
# attributes coloured by its stylesheet, and an inline style attribute passed
# through here was CSS injection in every consumer that renders stored HTML.
ATTRIBUTES = {
    "*": {
        "class",
        "id",
        "title",
        "role",
        "aria-label",
        "aria-hidden",
        # common editor data-* attributes seen in stored HTML
        # (wildcards like data-* are NOT supported by nh3, so each is listed)
        "data-tight",
        "data-node-type",
        "data-type",
        "data-checked",
        "data-background-color",
        "data-text-color",
        "data-text-align",
        "data-name",
        "data-id",
        # callout attributes
        "data-icon-name",
        "data-icon-color",
        "data-background",
        "data-emoji-unicode",
        "data-emoji-url",
        "data-logo-in-use",
        "data-block-type",
    },
    "a": {"href", "target"},
    "ol": {"start", "type"},
    # editor node/tag attributes
    "image-component": {
        "id",
        "width",
        "height",
        "aspectRatio",
        "aspectratio",
        "src",
        "alignment",
        "status",
    },
    "img": {
        "width",
        "height",
        "aspectRatio",
        "aspectratio",
        "alignment",
        "src",
        "alt",
        "title",
    },
    "mention-component": {"id", "entity_identifier", "entity_name"},
    "th": {
        "colspan",
        "rowspan",
        "colwidth",
        "background",
    },
    "td": {
        "colspan",
        "rowspan",
        "colwidth",
        "background",
        "textColor",
        "textcolor",
    },
    "tr": {"background", "textColor", "textcolor"},
    "pre": {"language"},
    "code": {"language", "spellcheck"},
    "input": {"type", "checked"},
}

# Attribute values. nh3 checks attribute names and URL schemes but not
# values, and several of these values are turned into CSS, classes or URLs by
# whoever renders the HTML. Keep in step with the editor's
# packages/editor/src/core/helpers/attribute-guards.ts and COLORS_LIST
# (packages/editor/src/core/constants/common.ts); a test checks the keys.
EDITOR_COLOR_KEYS = frozenset({"gray", "peach", "pink", "orange", "green", "light-blue", "dark-blue", "purple"})
EDITOR_TEXT_ALIGNMENTS = frozenset({"left", "center", "right"})
_EDITOR_COLOR_VARIABLE = re.compile(r"^var\(--editor-colors-([a-z-]+)-(?:text|background)\)$")
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_NUMBER = re.compile(r"^[0-9]{1,6}$")
_DIMENSION = re.compile(r"^[0-9]{1,6}(?:\.[0-9]{1,20})?(?:px|%)?$")
_COLUMN_WIDTHS = re.compile(r"^[0-9]{1,5}(?:,[0-9]{1,5}){0,63}$")
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{3,8}$")
_EMOJI_CODEPOINTS = re.compile(r"^[0-9a-fA-F]{1,8}(?:-[0-9a-fA-F]{1,8}){0,15}$")
_CLASS_TOKEN = re.compile(r"^(?:editor-[a-z0-9-]+|language-[A-Za-z0-9_+-]{1,64})$")
_HTTP_URL = re.compile(r"^https?://", re.IGNORECASE)

COLOR_KEY_ATTRIBUTES = frozenset(
    {"data-background-color", "data-text-color", "data-background", "background", "textcolor"}
)
TOKEN_ATTRIBUTES = frozenset(
    {
        "data-node-type",
        "data-type",
        "data-name",
        "data-icon-name",
        "data-block-type",
        "entity_name",
        "status",
        "role",
        "language",
    }
)
BOOLEAN_ATTRIBUTES = frozenset({"data-tight", "data-checked", "checked", "spellcheck", "aria-hidden"})
NUMBER_ATTRIBUTES = frozenset({"colspan", "rowspan", "start"})
DIMENSION_ATTRIBUTES = frozenset({"width", "height", "aspectratio"})


def sanitize_color_key(value):
    """A palette key, or None. The legacy CSS-variable form maps to its key."""
    value = (value or "").strip()
    if value in EDITOR_COLOR_KEYS:
        return value
    match = _EDITOR_COLOR_VARIABLE.match(value)
    if match and match.group(1) in EDITOR_COLOR_KEYS:
        return match.group(1)
    return None


def _filter_attribute_value(element, attribute, value):
    """nh3 attribute_filter: return the value to keep, or None to drop it."""
    attribute = attribute.lower()
    if attribute in COLOR_KEY_ATTRIBUTES:
        return sanitize_color_key(value)
    if attribute == "data-text-align" or attribute == "alignment":
        return value if value in EDITOR_TEXT_ALIGNMENTS else None
    if attribute in ("id", "data-id", "entity_identifier"):
        # Asset, mention and block ids are UUIDs. Anything else is a name that
        # can clobber a global in a page that renders this HTML.
        return value if _UUID.match(value) else None
    if attribute in TOKEN_ATTRIBUTES:
        return value if _TOKEN.match(value) else None
    if attribute in BOOLEAN_ATTRIBUTES:
        return value if value in ("", "true", "false", "checked") else None
    if attribute in NUMBER_ATTRIBUTES:
        return value if _NUMBER.match(value) else None
    if attribute in DIMENSION_ATTRIBUTES:
        return value if _DIMENSION.match(value) else None
    if attribute == "colwidth":
        return value if _COLUMN_WIDTHS.match(value) else None
    if attribute == "data-icon-color":
        return value if _HEX_COLOR.match(value) else None
    if attribute == "data-emoji-unicode":
        return value if _EMOJI_CODEPOINTS.match(value) else None
    if attribute == "data-logo-in-use":
        return value if value in ("emoji", "icon") else None
    if attribute == "data-emoji-url":
        return value if _HTTP_URL.match(value) else None
    if attribute == "type":
        # Task-list checkboxes and ordered-list numbering only; never a text or
        # password field inside someone else's content.
        if element == "input":
            return value if value == "checkbox" else None
        return value if value in ("1", "a", "A", "i", "I") else None
    if attribute == "target":
        return "_blank"
    if attribute == "src" and element == "image-component":
        # An API-issued asset id, or an absolute http(s) URL for older content.
        return value if _UUID.match(value) or _HTTP_URL.match(value) else None
    if attribute == "class":
        # Editor-owned classes only; a utility class such as `fixed inset-0`
        # would otherwise lay user content over the application.
        tokens = [token for token in value.split() if _CLASS_TOKEN.match(token)]
        return " ".join(tokens) or None
    return value


SAFE_PROTOCOLS = {"http", "https", "mailto", "tel"}


def _compute_html_sanitization_diff(before_html: str, after_html: str):
    """
    Compute a coarse diff between original and sanitized HTML.

    Returns a dict with:
    - removed_tags: mapping[tag] -> removed_count
    - removed_attributes: mapping[tag] -> sorted list of attribute names removed
    """
    try:

        def collect(soup):
            tag_counts = defaultdict(int)
            attrs_by_tag = defaultdict(set)
            for el in soup.find_all(True):
                tag_name = (el.name or "").lower()
                if not tag_name:
                    continue
                tag_counts[tag_name] += 1
                for attr_name in list(el.attrs.keys()):
                    if isinstance(attr_name, str) and attr_name:
                        attrs_by_tag[tag_name].add(attr_name.lower())
            return tag_counts, attrs_by_tag

        soup_before = BeautifulSoup(before_html or "", "html.parser")
        soup_after = BeautifulSoup(after_html or "", "html.parser")

        counts_before, attrs_before = collect(soup_before)
        counts_after, attrs_after = collect(soup_after)

        removed_tags = {}
        for tag, cnt_before in counts_before.items():
            cnt_after = counts_after.get(tag, 0)
            if cnt_after < cnt_before:
                removed = cnt_before - cnt_after
                removed_tags[tag] = removed

        removed_attributes = {}
        for tag, before_set in attrs_before.items():
            after_set = attrs_after.get(tag, set())
            removed = before_set - after_set
            if removed:
                removed_attributes[tag] = sorted(list(removed))

        return {"removed_tags": removed_tags, "removed_attributes": removed_attributes}
    except Exception:
        # Best-effort only; if diffing fails we don't block the request
        return {"removed_tags": {}, "removed_attributes": {}}


def validate_html_content(html_content: str):
    """
    Sanitize HTML content using nh3.
    Returns a tuple: (is_valid, error_message, clean_html)
    """
    if not html_content:
        return True, None, None

    # Size check - 10MB limit (consistent with binary validation)
    if len(html_content.encode("utf-8")) > MAX_SIZE:
        return False, "HTML content exceeds maximum size limit (10MB)", None

    try:
        clean_html = nh3.clean(
            html_content,
            tags=ALLOWED_TAGS,
            attributes=ATTRIBUTES,
            attribute_filter=_filter_attribute_value,
            url_schemes=SAFE_PROTOCOLS,
        )
        # Report removals to logger (Sentry) if anything was stripped
        diff = _compute_html_sanitization_diff(html_content, clean_html)
        if diff.get("removed_tags") or diff.get("removed_attributes"):
            try:
                import json

                summary = json.dumps(diff)
            except Exception:
                summary = str(diff)
            logger.warning(f"HTML sanitization removals: {summary}")
        return True, None, clean_html
    except Exception as e:
        log_exception(e)
        return False, "Failed to sanitize HTML", None


# User content embedded in notification e-mails. Narrower than the editor
# allowlist: no class, id, style, form controls or images, because the result
# is inserted into the message with `|safe` and read in mail clients that
# honour inline CSS and render forms.
EMAIL_FRAGMENT_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "del",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
}
EMAIL_FRAGMENT_ATTRIBUTES = {"a": {"href"}}
EMAIL_FRAGMENT_PROTOCOLS = {"http", "https", "mailto"}


def sanitize_email_fragment(html_content):
    """Sanitize a piece of user HTML for insertion into an e-mail template."""
    if not html_content:
        return ""
    try:
        return nh3.clean(
            str(html_content),
            tags=EMAIL_FRAGMENT_TAGS,
            attributes=EMAIL_FRAGMENT_ATTRIBUTES,
            url_schemes=EMAIL_FRAGMENT_PROTOCOLS,
            link_rel="noopener noreferrer nofollow",
            strip_comments=True,
        )
    except Exception as e:
        log_exception(e)
        return ""

def has_alphanumeric(value):
    """
    Check whether a string contains at least one alphanumeric character.

    `str.isalnum()` is Unicode-aware, so letters and digits from any script
    (Latin, CJK, Arabic, Cyrillic, etc.) all count. This mirrors the frontend
    HAS_ALPHANUMERIC_REGEX (/[\\p{L}\\p{N}]/u) check and is used to reject
    symbol-only names such as "-_________-".

    Args:
        value (str): The string to check.

    Returns:
        bool: True if the value contains at least one letter or digit.
    """
    return any(char.isalnum() for char in (value or ""))
