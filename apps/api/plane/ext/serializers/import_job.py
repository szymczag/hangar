# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Module imports
from plane.app.serializers.base import BaseSerializer
from plane.app.serializers.project import ProjectLiteSerializer
from plane.app.serializers.user import UserLiteSerializer

from plane.ext.models import ImportJob


class ImportJobSerializer(BaseSerializer):
    initiated_by_detail = UserLiteSerializer(source="initiated_by", read_only=True)
    project_detail = ProjectLiteSerializer(source="project", read_only=True)

    class Meta:
        model = ImportJob
        fields = [
            "id",
            "provider",
            "status",
            "project",
            "project_detail",
            "initiated_by",
            "initiated_by_detail",
            "stats",
            "errors",
            "reason",
            "attempt_count",
            "retry_of",
            "started_at",
            "cancel_requested_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
