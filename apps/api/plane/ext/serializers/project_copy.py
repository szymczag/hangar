# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import re

from rest_framework import serializers

from plane.db.models import Project, ProjectNetwork
from plane.ext.models import ProjectCopyJob
from plane.ext.services.project_copy import COPY_OPTIONS
from plane.ext.utils.plain_text import PlainTextError, validate_single_line_text


class ProjectCopyOptionsSerializer(serializers.Serializer):
    """What to carry across.

    Declared field by field rather than as a free-form JSONField: the opt-in
    surface of a copy should be auditable, and an unknown key is a mistake worth
    reporting rather than a silently ignored no-op.
    """

    states = serializers.BooleanField(required=False)
    work_item_types = serializers.BooleanField(required=False)
    labels = serializers.BooleanField(required=False)
    estimates = serializers.BooleanField(required=False)
    intake = serializers.BooleanField(required=False)
    members = serializers.BooleanField(required=False)
    cycles = serializers.BooleanField(required=False)
    modules = serializers.BooleanField(required=False)
    views = serializers.BooleanField(required=False)
    work_items = serializers.BooleanField(required=False)

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("include must be an object")

        unknown = sorted(set(data) - set(COPY_OPTIONS))
        if unknown:
            raise serializers.ValidationError(f"Unknown copy option(s): {', '.join(unknown)}")

        return super().to_internal_value(data)


class ProjectDuplicateSerializer(serializers.Serializer):
    """Request body for duplicating a project.

    Every field is optional; the service derives a free name and identifier and
    inherits the source's visibility when they are omitted.
    """

    name = serializers.CharField(required=False, allow_blank=False, max_length=255)
    identifier = serializers.CharField(required=False, allow_blank=False, max_length=12)
    network = serializers.ChoiceField(required=False, choices=ProjectNetwork.choices())
    include = ProjectCopyOptionsSerializer(required=False)

    def validate_name(self, name):
        # The duplicate modal prefills "<source> (Copy)", and parentheses are in
        # the identifier pattern this used to apply -- so the modal's own default
        # was rejected by this endpoint and duplication never worked from the
        # interface at all. A display name is held to what one line of human text
        # must be; the identifier below keeps the strict pattern.
        try:
            return validate_single_line_text(name, max_length=255, field="Project name")
        except PlainTextError:
            raise serializers.ValidationError("PROJECT_NAME_CANNOT_CONTAIN_SPECIAL_CHARACTERS")

    def validate_identifier(self, identifier):
        identifier = identifier.strip().upper()
        if re.match(Project.FORBIDDEN_IDENTIFIER_CHARS_PATTERN, identifier):
            raise serializers.ValidationError("PROJECT_IDENTIFIER_CANNOT_CONTAIN_SPECIAL_CHARACTERS")
        return identifier


class ProjectCopyJobSerializer(serializers.ModelSerializer):
    """What the interface needs to report a copy in progress.

    Read-only throughout: nothing about a running copy is client-settable. The
    lease, the cursor and the stored translation are machinery and are not
    exposed -- progress is `copied` against `total`, and the outcome is `status`
    plus `counts` and `skipped`.
    """

    class Meta:
        model = ProjectCopyJob
        fields = [
            "id",
            "status",
            "stage",
            "total",
            "copied",
            "counts",
            "skipped",
            "errors",
            "reason",
            "started_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields
