# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third Party Imports
from rest_framework import serializers

# Module imports
from .base import BaseSerializer
from .user import UserLiteSerializer
from plane.db.models import FileAsset, Workspace
from plane.utils.constants import RESTRICTED_WORKSPACE_SLUGS
from plane.utils.content_validator import has_alphanumeric
from plane.utils.url import contains_url


class WorkspaceSerializer(BaseSerializer):
    owner = UserLiteSerializer(read_only=True)
    logo_url = serializers.CharField(read_only=True)
    total_projects = serializers.IntegerField(read_only=True)
    total_members = serializers.IntegerField(read_only=True)

    def validate_name(self, value):
        # Check if the name contains a URL (kept consistent with the app-level
        # WorkSpaceSerializer so both workspace-create paths validate alike).
        if contains_url(value):
            raise serializers.ValidationError("Name must not contain URLs")
        # Reject symbol-only names like "-_________-" that have no letter or
        # digit. Mirrors the frontend HAS_ALPHANUMERIC_REGEX check so the rule
        # cannot be bypassed via a direct API call.
        if not has_alphanumeric(value):
            raise serializers.ValidationError(
                "Name must contain at least one letter or number"
            )
        return value

    def validate_logo_asset(self, value):
        """Only this workspace's own logo asset may be named here, or none.

        Mirrors the app-level WorkSpaceSerializer: the next logo upload
        soft-deletes whatever this field points at, so a new workspace starts
        without one.
        """
        if value is None:
            return value
        if (
            self.instance is None
            or value.entity_type != FileAsset.EntityTypeContext.WORKSPACE_LOGO
            or value.workspace_id != self.instance.id
        ):
            raise serializers.ValidationError("Choose a logo uploaded for this workspace.")
        return value

    def validate_slug(self, value):
        # Check if the slug is restricted
        if value in RESTRICTED_WORKSPACE_SLUGS:
            raise serializers.ValidationError("Slug is not valid")
        # Check uniqueness case-insensitively
        if Workspace.objects.filter(slug__iexact=value).exists():
            raise serializers.ValidationError("Slug is already in use")
        return value

    class Meta:
        model = Workspace
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "owner",
            "logo_url",
        ]
