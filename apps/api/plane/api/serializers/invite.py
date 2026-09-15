# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from rest_framework import serializers

# Module imports
from plane.authentication.utils.sso_domain_policy import invitation_rejection_reason
from plane.db.models import WorkspaceMemberInvite
from .base import BaseSerializer
from plane.app.permissions.base import ROLE


class WorkspaceInviteSerializer(BaseSerializer):
    """
    Serializer for workspace invites.
    """

    class Meta:
        model = WorkspaceMemberInvite
        fields = [
            "id",
            "email",
            "role",
            "created_at",
            "updated_at",
            "responded_at",
            "accepted",
        ]
        read_only_fields = [
            "id",
            "workspace",
            "created_at",
            "updated_at",
            "responded_at",
            "accepted",
        ]

    def validate_email(self, value):
        try:
            validate_email(value)
        except ValidationError:
            raise serializers.ValidationError("Invalid email address", code="INVALID_EMAIL_ADDRESS")
        # The same domain policy the app endpoints apply. Without it the v1 API
        # is a way around the restriction the operator configured.
        rejection = invitation_rejection_reason(value)
        if rejection:
            raise serializers.ValidationError(rejection, code="EMAIL_NOT_INVITABLE")
        return value

    def validate_role(self, value):
        if value not in [ROLE.ADMIN.value, ROLE.MEMBER.value, ROLE.GUEST.value]:
            raise serializers.ValidationError("Invalid role", code="INVALID_WORKSPACE_MEMBER_ROLE")
        return value

    def validate(self, data):
        slug = self.context["slug"]
        if (
            data.get("email")
            and WorkspaceMemberInvite.objects.filter(email=data["email"], workspace__slug=slug).exists()
        ):
            raise serializers.ValidationError("Email already invited", code="EMAIL_ALREADY_INVITED")
        return data
