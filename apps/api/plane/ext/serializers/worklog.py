# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.ext.models import IssueWorkLog


class IssueWorkLogSerializer(serializers.ModelSerializer):
    description = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    class Meta:
        model = IssueWorkLog
        fields = [
            "id",
            "duration",
            "description",
            "logged_by",
            "issue",
            "project",
            "workspace",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "logged_by", "issue", "project", "workspace", "created_at", "updated_at"]
