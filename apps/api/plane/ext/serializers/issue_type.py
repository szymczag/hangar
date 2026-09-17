# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import IssueType
from plane.ext.models import EpicUserProperty


class EpicSettingsSerializer(serializers.Serializer):
    is_epic_enabled = serializers.BooleanField()


LOGO_TEXT_MAX_LENGTH = 64


def _logo_text(value, field):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > LOGO_TEXT_MAX_LENGTH:
        raise serializers.ValidationError(f"{field} must be text of at most {LOGO_TEXT_MAX_LENGTH} characters")
    return value


class IssueTypeSerializer(serializers.ModelSerializer):
    def validate_logo_props(self, value):
        """Accept only the emoji/icon shape the web logo renderer understands."""

        if value in (None, {}):
            return {}
        if not isinstance(value, dict) or value.get("in_use") not in {"emoji", "icon"}:
            raise serializers.ValidationError("in_use must be 'emoji' or 'icon'")
        if set(value) - {"in_use", "emoji", "icon"}:
            raise serializers.ValidationError("Unsupported logo field")

        in_use = value["in_use"]
        detail = value.get(in_use)
        if not isinstance(detail, dict):
            raise serializers.ValidationError(f"{in_use} details are required")

        if in_use == "emoji":
            allowed = {"value", "url"}
        else:
            allowed = {"name", "color", "background_color"}
        if set(detail) - allowed:
            raise serializers.ValidationError(f"Unsupported {in_use} field")
        clean = {key: _logo_text(detail.get(key), f"{in_use}.{key}") for key in allowed if key in detail}
        primary = "value" if in_use == "emoji" else "name"
        if not clean.get(primary):
            raise serializers.ValidationError(f"{in_use}.{primary} is required")
        return {"in_use": in_use, in_use: clean}

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
            "system_key",
            "workspace",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "workspace",
            "is_epic",
            "is_default",
            "level",
            "system_key",
            "created_at",
            "updated_at",
        ]


class EpicUserPropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = EpicUserProperty
        fields = ["filters", "display_filters", "display_properties", "rich_filters", "preferences", "sort_order"]
