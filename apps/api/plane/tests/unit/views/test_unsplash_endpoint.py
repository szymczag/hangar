# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from types import SimpleNamespace

import pytest
import requests

from plane.app.views.external.base import UnsplashEndpoint


def _request(**params):
    return SimpleNamespace(GET=params)


def _configured_endpoint(mocker):
    mocker.patch(
        "plane.app.views.external.base.get_configuration_value",
        return_value=("access-key",),
    )
    return UnsplashEndpoint()


@pytest.mark.unit
def test_unsplash_search_uses_structured_params_and_pinned_transport(mocker):
    endpoint = _configured_endpoint(mocker)
    upstream = mocker.Mock(status_code=200)
    upstream.json.return_value = {"results": []}
    pinned_fetch = mocker.patch(
        "plane.app.views.external.base.pinned_fetch", return_value=upstream
    )

    response = endpoint.get(
        _request(query="cats&redirect=http://127.0.0.1", page="2", per_page="30")
    )

    assert response.status_code == 200
    pinned_fetch.assert_called_once_with(
        "GET",
        "https://api.unsplash.com/search/photos",
        headers={
            "Accept": "application/json",
            "Authorization": "Client-ID access-key",
        },
        params={
            "query": "cats&redirect=http://127.0.0.1",
            "page": 2,
            "per_page": 30,
        },
        timeout=10,
    )


@pytest.mark.unit
def test_unsplash_list_uses_fixed_origin_and_defaults(mocker):
    endpoint = _configured_endpoint(mocker)
    upstream = mocker.Mock(status_code=200)
    upstream.json.return_value = []
    pinned_fetch = mocker.patch(
        "plane.app.views.external.base.pinned_fetch", return_value=upstream
    )

    response = endpoint.get(_request())

    assert response.status_code == 200
    assert pinned_fetch.call_args.kwargs["params"] == {"page": 1, "per_page": 20}
    assert pinned_fetch.call_args.args[1] == "https://api.unsplash.com/photos"


@pytest.mark.unit
@pytest.mark.parametrize(
    "params",
    [
        {"page": "0"},
        {"page": "not-a-number"},
        {"page": "10001"},
        {"per_page": "0"},
        {"per_page": "31"},
    ],
)
def test_unsplash_rejects_invalid_pagination(mocker, params):
    endpoint = _configured_endpoint(mocker)
    pinned_fetch = mocker.patch("plane.app.views.external.base.pinned_fetch")

    response = endpoint.get(_request(**params))

    assert response.status_code == 400
    pinned_fetch.assert_not_called()


@pytest.mark.unit
def test_unsplash_rejects_redirects(mocker):
    endpoint = _configured_endpoint(mocker)
    upstream = mocker.Mock(status_code=302)
    mocker.patch("plane.app.views.external.base.pinned_fetch", return_value=upstream)

    response = endpoint.get(_request())

    assert response.status_code == 502
    upstream.close.assert_called_once_with()
    upstream.json.assert_not_called()


@pytest.mark.unit
def test_unsplash_handles_transport_failure(mocker):
    endpoint = _configured_endpoint(mocker)
    mocker.patch(
        "plane.app.views.external.base.pinned_fetch",
        side_effect=requests.ConnectionError("unreachable"),
    )
    mocker.patch("plane.app.views.external.base.log_exception")

    response = endpoint.get(_request())

    assert response.status_code == 502


@pytest.mark.unit
def test_unsplash_without_access_key_does_not_make_request(mocker):
    mocker.patch(
        "plane.app.views.external.base.get_configuration_value", return_value=(None,)
    )
    pinned_fetch = mocker.patch("plane.app.views.external.base.pinned_fetch")

    response = UnsplashEndpoint().get(_request())

    assert response.status_code == 200
    assert response.data == []
    pinned_fetch.assert_not_called()
