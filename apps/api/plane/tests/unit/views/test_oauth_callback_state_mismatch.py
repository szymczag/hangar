# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Regression tests for the OAuth callback views that read the host back out of
the session.

Assigning ``base_host = request.session.get("host")`` inside the callback
shadowed the imported ``base_host()`` helper, so every later
``base_host(request=...)`` call in the same method raised
``TypeError: 'str' object is not callable`` and no OAuth login on the affected
views could complete.

Hangar keeps the host, next path and state in a per-provider OAuth transaction
(``plane.authentication.utils.oauth_transaction``) rather than in loose session
keys, so the session here holds that transaction. A bad state must still
redirect back to the space app with an error, and must use up the transaction.

See: https://github.com/makeplane/plane/issues/9159
See: https://github.com/makeplane/plane/issues/9164
"""

import time

import pytest
from django.http import HttpResponseRedirect
from django.test import RequestFactory, override_settings

from plane.authentication.views.space.gitea import GITEA_TRANSACTION_SPACE, GiteaCallbackSpaceEndpoint
from plane.authentication.views.space.github import GITHUB_TRANSACTION_SPACE, GitHubCallbackSpaceEndpoint
from plane.authentication.views.space.gitlab import GITLAB_TRANSACTION_SPACE, GitLabCallbackSpaceEndpoint
from plane.authentication.views.space.google import GOOGLE_TRANSACTION_SPACE, GoogleCallbackSpaceEndpoint

CALLBACK_VIEWS = [
    (GiteaCallbackSpaceEndpoint, GITEA_TRANSACTION_SPACE),
    (GitHubCallbackSpaceEndpoint, GITHUB_TRANSACTION_SPACE),
    (GitLabCallbackSpaceEndpoint, GITLAB_TRANSACTION_SPACE),
    (GoogleCallbackSpaceEndpoint, GOOGLE_TRANSACTION_SPACE),
]


def _callback_request(session):
    request = RequestFactory().get("/auth/callback/", {"code": "abc", "state": "wrong"})
    request.session = session
    return request


@pytest.mark.unit
@pytest.mark.parametrize("view_class, transaction_key", CALLBACK_VIEWS, ids=lambda v: getattr(v, "__name__", v))
@override_settings(WEB_URL="http://localhost", SPACE_BASE_URL=None)
def test_state_mismatch_redirects_with_error(view_class, transaction_key):
    """A bad state must redirect back to the app with an error, not crash."""
    request = _callback_request(
        {
            transaction_key: {
                "state": "expected",
                "host": "http://localhost/spaces/",
                "next_path": "",
                "created_at": time.time(),
            }
        }
    )

    response = view_class().get(request)

    assert isinstance(response, HttpResponseRedirect)
    assert response.url.startswith("http://localhost/spaces/")
    assert "error_code" in response.url
    # The transaction is single-use: a failed attempt consumes it too.
    assert transaction_key not in request.session


@pytest.mark.unit
@pytest.mark.parametrize("view_class, transaction_key", CALLBACK_VIEWS, ids=lambda v: getattr(v, "__name__", v))
@override_settings(WEB_URL="http://localhost", SPACE_BASE_URL=None)
def test_missing_transaction_redirects_with_error(view_class, transaction_key):
    """Without a transaction the host falls back to ``base_host()``, which must still be callable."""
    response = view_class().get(_callback_request({}))

    assert isinstance(response, HttpResponseRedirect)
    assert response.url.startswith("http://localhost/spaces/")
    assert "error_code" in response.url
