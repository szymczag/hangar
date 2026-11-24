# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Logging contract for ``handle_exception()`` on the shared base views.

A missing object is an ordinary 404. It must not leave a "Server Error" line on
stdout (operators grep for that) and must not reach the exception logger. A
genuinely unhandled error still answers 500 and goes through ``log_exception``.
"""

import pytest
from unittest.mock import patch

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.renderers import JSONRenderer
from rest_framework.test import APIRequestFactory

from plane.api.views.base import BaseAPIView as ApiBaseAPIView, BaseViewSet as ApiBaseViewSet
from plane.app.views.base import BaseAPIView as AppBaseAPIView, BaseViewSet as AppBaseViewSet
from plane.license.api.views.base import BaseAPIView as LicenseBaseAPIView
from plane.space.views.base import BaseAPIView as SpaceBaseAPIView, BaseViewSet as SpaceBaseViewSet

VIEW_CLASSES = [
    ApiBaseAPIView,
    ApiBaseViewSet,
    AppBaseAPIView,
    AppBaseViewSet,
    LicenseBaseAPIView,
    SpaceBaseAPIView,
    SpaceBaseViewSet,
]


def _view(view_class):
    view = view_class()
    # ViewSets resolve self.action from the router's action map.
    view.action_map = {"get": "list"}
    request = view.initialize_request(APIRequestFactory().get("/api/test/"))
    request.accepted_renderer = JSONRenderer()
    view.request = request
    view.args = ()
    view.kwargs = {}
    view.headers = {}
    view.format_kwarg = None
    return view


@pytest.mark.unit
@pytest.mark.parametrize("view_class", VIEW_CLASSES, ids=lambda c: f"{c.__module__}.{c.__name__}")
def test_missing_object_is_a_quiet_404(view_class, capsys):
    view = _view(view_class)

    with patch(f"{view_class.__module__}.log_exception") as mock_log:
        response = view.handle_exception(ObjectDoesNotExist("gone"))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    captured = capsys.readouterr()
    assert "Server Error" not in captured.out
    assert "Server Error" not in captured.err
    mock_log.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize("view_class", VIEW_CLASSES, ids=lambda c: f"{c.__module__}.{c.__name__}")
def test_unhandled_error_is_logged_as_500(view_class, capsys):
    view = _view(view_class)
    error = RuntimeError("boom")

    with patch(f"{view_class.__module__}.log_exception") as mock_log:
        response = view.handle_exception(error)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    mock_log.assert_called_once_with(error)
    assert "Server Error" not in capsys.readouterr().out
