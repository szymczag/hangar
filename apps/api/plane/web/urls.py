# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path
from plane.web.views import csp_report, robots_txt, health_check

urlpatterns = [
    path("robots.txt", robots_txt),
    path("api/csp-report/", csp_report),
    path("", health_check),
]
