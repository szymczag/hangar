# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The role a workspace membership needs before it can mint an API token.

Kept here rather than beside the endpoint that enforces it, because the
application has to ask the same question: an interface that offers to create a
token where the answer is no sends people to a refusal it could have predicted.
"""

import os

from plane.license.utils.instance_value import get_configuration_value

# Guest. The default keeps the feature working as it did, and an operator
# raises it.
DEFAULT_MINIMUM_ROLE = 5


def api_token_minimum_role() -> int:
    (configured,) = get_configuration_value(
        [
            {
                "key": "API_TOKEN_MINIMUM_ROLE",
                "default": os.environ.get("API_TOKEN_MINIMUM_ROLE", str(DEFAULT_MINIMUM_ROLE)),
            }
        ]
    )
    try:
        return int(configured)
    except (TypeError, ValueError):
        # An unreadable setting must not hand out tokens more freely than the
        # administrator intended, but it also must not lock everyone out of a
        # feature that worked yesterday.
        return DEFAULT_MINIMUM_ROLE
