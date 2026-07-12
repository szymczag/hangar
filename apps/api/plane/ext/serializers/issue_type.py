# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import IssueType
from plane.ext.models import EpicUserProperty


class EpicSettingsSerializer(serializers.Serializer):
    is_epic_enabled = serializers.BooleanField()


class IssueTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueType
        fields = [
            "id",
            "name",
            "description",
            "logo_props",
            "is_epic",
            "is_default",
            "is_active",
            "level",
            "workspace",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace", "created_at", "updated_at"]


class EpicUserPropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = EpicUserProperty
        fields = ["filters", "display_filters", "display_properties", "rich_filters", "preferences", "sort_order"]
