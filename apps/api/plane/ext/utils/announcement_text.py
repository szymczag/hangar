# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Validation for operator-authored text that is shown to people verbatim.

Kept apart from the one endpoint that uses it today because it is not the only
place that needs it: `INSTANCE_SUPPORT_TEXT` reaches the failure pages with no
length cap and no character validation at all.
"""

# Python imports
import unicodedata


class AnnouncementTextError(ValueError):
    """The text is not safe or reasonable to render."""


def validate_announcement_text(value, *, max_length=500, field="Message"):
    """Return `value` stripped, or raise `AnnouncementTextError`.

    Rejects every character in the Unicode categories `Cc` (control) and `Cf`
    (format). That covers newlines and tabs in a single strip of text, and more
    importantly it covers the bidirectional overrides: U+202E in a banner
    rendered above the entire application can make "maintenance at 22:00" read
    as something else entirely, and no amount of HTML escaping downstream would
    help, because the characters are not markup.
    """
    text = (value or "").strip()

    if len(text) > max_length:
        raise AnnouncementTextError(f"{field} must be {max_length} characters or fewer.")

    for character in text:
        if unicodedata.category(character) in {"Cc", "Cf"}:
            raise AnnouncementTextError(
                f"{field} cannot contain control or formatting characters, including line breaks."
            )

    return text
