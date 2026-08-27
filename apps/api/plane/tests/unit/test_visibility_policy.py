# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The private value named for each model must be the one that model means.

Three models carry a visibility field and disagree about the numbers. Page uses
0 for public and 1 for private; IssueView uses the reverse. A constant that
drifts from its model — through a renumbering upstream, or a copied line — would
not fail loudly: it would quietly publish what it was asked to hide.
"""

import pytest

from plane.db.models import Page, Project
from plane.db.models.view import IssueView
from plane.utils.visibility_policy import (
    PAGE_PRIVATE_ACCESS,
    PROJECT_SECRET_NETWORK,
    VIEW_PRIVATE_ACCESS,
)


def _choice_labels(field):
    return {value: str(label).lower() for value, label in field.choices}


@pytest.mark.unit
def test_the_project_value_is_the_one_the_model_calls_secret():
    labels = _choice_labels(Project._meta.get_field("network"))

    assert labels[PROJECT_SECRET_NETWORK] == "secret"


@pytest.mark.unit
def test_the_page_value_is_the_one_the_model_calls_private():
    labels = _choice_labels(Page._meta.get_field("access"))

    assert labels[PAGE_PRIVATE_ACCESS] == "private"


@pytest.mark.unit
def test_the_view_value_is_the_one_the_model_calls_private():
    labels = _choice_labels(IssueView._meta.get_field("access"))

    assert labels[VIEW_PRIVATE_ACCESS] == "private"


@pytest.mark.unit
def test_page_and_view_really_do_disagree():
    """If this ever stops being true, the separate constants can go.

    Until then they are the reason this module exists, and a reader who assumes
    one value works for both is wrong.
    """
    assert PAGE_PRIVATE_ACCESS != VIEW_PRIVATE_ACCESS
