# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.license.api.views.admin import _form_boolean_is_enabled


@pytest.mark.unit
@pytest.mark.parametrize("value", [True, "1", "true", "TRUE", "yes", "on"])
def test_form_boolean_accepts_explicit_opt_in_values(value):
    assert _form_boolean_is_enabled(value) is True


@pytest.mark.unit
@pytest.mark.parametrize("value", [False, None, "", "0", "false", "off", "unexpected"])
def test_form_boolean_rejects_absent_or_false_values(value):
    assert _form_boolean_is_enabled(value) is False
