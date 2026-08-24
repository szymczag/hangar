# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from rest_framework.permissions import BasePermission

# Module imports
from plane.license.models import Instance, InstanceAdmin


class InstanceAdminPermission(BasePermission):
    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False

        instance = Instance.objects.first()
        if not InstanceAdmin.objects.filter(role__gte=15, instance=instance, user=request.user).exists():
            return False

        # Fork (see FORK.md): the console requires a second factor. Checked here
        # as well as by leaving the password step anonymous, so that "this
        # session proved a security key" is an invariant every future code path
        # creating an admin session must also satisfy — including sessions that
        # already existed when this shipped, which are now unverified.
        from plane.ext.auth.webauthn.pending import is_verified

        return is_verified(request.session)
