# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""``validate_upload_metadata`` turns every unusable size into a validation error.

A JSON size such as ``1e400`` parses to ``float("inf")``. ``int()`` then raises
``OverflowError``, which escaped the ``TypeError``/``ValueError`` handler and
surfaced as HTTP 500 on every upload endpoint.
"""

import json

import pytest

from plane.utils.file_asset_upload import UploadError, validate_upload_metadata


def _validate(size):
    return validate_upload_metadata(raw_name="report.pdf", raw_size=size, claimed_mime_type="application/pdf")


@pytest.mark.unit
def test_numeric_string_size_is_accepted():
    assert _validate("1024").size == 1024


@pytest.mark.unit
@pytest.mark.parametrize(
    "size",
    [
        json.loads("1e400"),
        float("inf"),
        float("-inf"),
        float("nan"),
        "inf",
        "1e400",
        "not-a-number",
        None,
        [],
    ],
    ids=["json-1e400", "inf", "-inf", "nan", "str-inf", "str-1e400", "text", "none", "list"],
)
def test_unusable_size_is_a_validation_error(size):
    with pytest.raises(UploadError) as excinfo:
        _validate(size)

    assert excinfo.value.code == "invalid_file_size"
    assert excinfo.value.http_status == 400
