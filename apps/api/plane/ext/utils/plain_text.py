# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Validation for human-authored text rendered on a single line.

One rule, in one place, for every field of this shape: a maintenance notice, a
project name, and -- still to come -- `INSTANCE_SUPPORT_TEXT`, which reaches the
failure pages today with no length cap and no character validation at all.

It deliberately says nothing about punctuation. A display name is prose written
by a person and legitimately contains hyphens, dots, apostrophes, ampersands and
parentheses; the rule that forbids those belongs to identifiers, which end up in
URLs and work-item keys, and it does real damage when applied to a name.
"""

# Python imports
import unicodedata


class PlainTextError(ValueError):
    """The text is not safe or reasonable to render on one line."""


def validate_single_line_text(value, *, max_length=500, field="Message"):
    """Return `value` stripped, or raise `PlainTextError`.

    Rejects every character in the Unicode categories `Cc` (control) and `Cf`
    (format). That covers newlines and tabs in something meant to sit on one
    line, and more importantly it covers the bidirectional overrides: U+202E in
    a maintenance banner can make "maintenance at 22:00" read as something else
    entirely, and in a project name it reorders the text around it in every list
    the name appears in. No amount of HTML escaping downstream helps, because
    the characters are not markup.

    Note this is stricter than what it replaced for project names, which
    permitted newlines and bidi overrides while forbidding ordinary punctuation.
    """
    text = (value or "").strip()

    if len(text) > max_length:
        raise PlainTextError(f"{field} must be {max_length} characters or fewer.")

    for character in text:
        if unicodedata.category(character) in {"Cc", "Cf"}:
            raise PlainTextError(f"{field} cannot contain control or formatting characters, including line breaks.")

    return text
