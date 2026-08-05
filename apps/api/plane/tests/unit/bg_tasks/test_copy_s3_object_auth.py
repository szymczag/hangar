# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import MagicMock, patch

from django.test import override_settings

from plane.bgtasks.copy_s3_object import sync_with_external_service


LIVE_URL = "http://live:3000/live/"
SECRET = "unit-test-live-secret"


@override_settings(LIVE_URL=LIVE_URL, LIVE_SERVER_SECRET_KEY=SECRET)
def test_document_conversion_sends_secret_and_rejects_redirects():
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "description_json": {},
        "description_binary": "AA==",
    }

    with patch(
        "plane.bgtasks.copy_s3_object.requests.post", return_value=response
    ) as mock_post:
        result = sync_with_external_service("PAGE", "<p>hello</p>")

    assert result == {"description_json": {}, "description_binary": "AA=="}
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["headers"] == {
        "live-server-secret-key": SECRET
    }
    assert mock_post.call_args.kwargs["timeout"] == 10
    assert mock_post.call_args.kwargs["allow_redirects"] is False


@override_settings(LIVE_URL=LIVE_URL, LIVE_SERVER_SECRET_KEY=None)
def test_document_conversion_without_secret_skips_request_and_logs():
    with (
        patch("plane.bgtasks.copy_s3_object.requests.post") as mock_post,
        patch("plane.bgtasks.copy_s3_object.log_exception") as mock_log,
    ):
        result = sync_with_external_service("PAGE", "<p>hello</p>")

    assert result == {}
    mock_post.assert_not_called()
    mock_log.assert_called_once()


@override_settings(LIVE_URL=None, LIVE_SERVER_SECRET_KEY=SECRET)
def test_document_conversion_without_live_url_skips_request():
    with patch("plane.bgtasks.copy_s3_object.requests.post") as mock_post:
        result = sync_with_external_service("PAGE", "<p>hello</p>")

    assert result == {}
    mock_post.assert_not_called()


@override_settings(LIVE_URL=LIVE_URL, LIVE_SERVER_SECRET_KEY=SECRET)
def test_document_conversion_does_not_accept_redirect_as_success():
    with patch(
        "plane.bgtasks.copy_s3_object.requests.post",
        return_value=MagicMock(status_code=302),
    ):
        result = sync_with_external_service("PAGE", "<p>hello</p>")

    assert result == {}
