# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.ext.models import IssueProperty, IssuePropertyOption, PropertyTypeChoices


class IssuePropertyOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssuePropertyOption
        fields = [
            "id",
            "name",
            "sort_order",
            "is_active",
            "is_default",
            "logo_props",
            "property",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "property", "created_at", "updated_at"]


class IssuePropertySerializer(serializers.ModelSerializer):
    options = IssuePropertyOptionSerializer(many=True, read_only=True)

    class Meta:
        model = IssueProperty
        fields = [
            "id",
            "display_name",
            "description",
            "property_type",
            "is_multi",
            "is_required",
            "is_active",
            "default_value",
            "settings",
            "logo_props",
            "sort_order",
            "issue_type",
            "options",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "issue_type", "options", "created_at", "updated_at"]

    def validate(self, attrs):
        property_type = attrs.get("property_type", getattr(self.instance, "property_type", None))
        is_multi = attrs.get("is_multi", getattr(self.instance, "is_multi", False))
        if is_multi and property_type not in (
            PropertyTypeChoices.MULTI_SELECT,
            PropertyTypeChoices.MEMBER,
        ):
            raise serializers.ValidationError({"is_multi": "Only multi_select and member properties can be multi"})
        # The type of an existing property is immutable — changing it would
        # orphan the typed value column of every existing row.
        if self.instance and "property_type" in attrs and attrs["property_type"] != self.instance.property_type:
            raise serializers.ValidationError({"property_type": "Property type cannot be changed"})
        return attrs
