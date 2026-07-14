# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from .views import (
    RunnerInstallationEndpoint,
    RunnerInstallationRevokeEndpoint,
    RunnerInstallationSuspendEndpoint,
)

urlpatterns = [
    path(
        "installation/",
        RunnerInstallationEndpoint.as_view(),
        name="runner-installation",
    ),
    path(
        "installation/suspend/",
        RunnerInstallationSuspendEndpoint.as_view(),
        name="runner-installation-suspend",
    ),
    path(
        "installation/revoke/",
        RunnerInstallationRevokeEndpoint.as_view(),
        name="runner-installation-revoke",
    ),
]
