# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Query parameters a published board does not take because they name a person.

The board's work items carry no assignees and no creator (FORK.md, S30). A
filter on one would still answer "is this user assigned here?" for any user id
a visitor tries, grouping by one would list the ids as group keys, and ordering
by an assignee's name would rank the members. So these parameters are dropped
or refused before the shared issue helpers see them.
"""

PERSON_FILTER_PARAMS = frozenset({"assignees", "mentions", "created_by", "logged_by", "subscriber"})
PERSON_GROUP_BY = frozenset({"assignees__id", "created_by"})
PERSON_ORDER_BY = frozenset({"assignees__first_name"})
DEFAULT_ORDER_BY = "-created_at"


def public_filter_params(query_params):
    """The request's filter parameters without the ones keyed on a person."""
    return {key: value for key, value in query_params.items() if key not in PERSON_FILTER_PARAMS}


def public_order_by(value):
    """The requested ordering, or the default when it sorts by a person."""
    if value and value.lstrip("-") in PERSON_ORDER_BY:
        return DEFAULT_ORDER_BY
    return value


def is_person_grouping(*group_keys):
    return any(key in PERSON_GROUP_BY for key in group_keys if key)
