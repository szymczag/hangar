# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Whether workspace members, and not only admins, may invite people.

Kept beside the other instance policies rather than inside the permission
class, because the application has to ask the same question: an invite button
offered to someone the server will refuse is a form that is filled in and then
turned down.
"""

import os

from plane.license.utils.instance_value import get_configuration_value

ALLOW_MEMBERS_TO_INVITE_KEY = "ALLOW_MEMBERS_TO_INVITE"


def members_can_invite(raw_setting=None) -> bool:
    """True only when the operator has handed inviting to workspace members.

    Anything but an explicit "1" reads as off, so an unreadable or mistyped
    value keeps invitations with the admins rather than widening them.
    """
    if raw_setting is None:
        (raw_setting,) = get_configuration_value(
            [
                {
                    "key": ALLOW_MEMBERS_TO_INVITE_KEY,
                    "default": os.environ.get(ALLOW_MEMBERS_TO_INVITE_KEY, "0"),
                }
            ]
        )
    return str(raw_setting or "").strip() == "1"
