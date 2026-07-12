# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import transaction

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ROLE, allow_permission
from plane.app.views.base import BaseAPIView
from plane.db.models import Issue, IssueType
from plane.db.models.issue_type import ProjectIssueType

from plane.ext.models import IssueProperty, IssuePropertyOption, IssuePropertyValue, PropertyTypeChoices
from plane.ext.serializers.issue_property import IssuePropertyOptionSerializer, IssuePropertySerializer
from plane.ext.serializers.issue_type import IssueTypeSerializer
from plane.ext.utils.property_validators import validate_property_values


def project_issue_types(slug, project_id):
    """Issue types linked to this project, scoped through the workspace."""
    return IssueType.objects.filter(
        workspace__slug=slug,
        project_issue_types__project_id=project_id,
    ).distinct()


def scoped_property(slug, project_id, property_id):
    """A property reachable only through a type linked to this project."""
    return IssueProperty.objects.get(
        pk=property_id,
        workspace__slug=slug,
        issue_type__project_issue_types__project_id=project_id,
    )


class IssueTypesEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        issue_types = project_issue_types(slug, project_id).prefetch_related("properties__options")
        serializer = IssueTypeSerializer(issue_types, many=True)
        data = serializer.data
        if "properties" in request.GET.get("include", ""):
            properties_by_type = {}
            for issue_type in issue_types:
                properties_by_type[str(issue_type.id)] = IssuePropertySerializer(
                    issue_type.properties.filter(deleted_at__isnull=True), many=True
                ).data
            for item in data:
                item["properties"] = properties_by_type.get(str(item["id"]), [])
        return Response(data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def post(self, request, slug, project_id):
        from plane.db.models import Project

        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        serializer = IssueTypeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        # Custom types are never epics — the epic type is managed by the
        # epic-settings endpoint.
        issue_type = serializer.save(workspace=project.workspace, is_epic=False)
        ProjectIssueType.objects.create(project=project, issue_type=issue_type)
        return Response(IssueTypeSerializer(issue_type).data, status=status.HTTP_201_CREATED)


class IssueTypeDetailEndpoint(BaseAPIView):
    def get_type(self, slug, project_id, type_id):
        return project_issue_types(slug, project_id).get(pk=type_id)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, type_id):
        issue_type = self.get_type(slug, project_id, type_id)
        return Response(IssueTypeSerializer(issue_type).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def patch(self, request, slug, project_id, type_id):
        issue_type = self.get_type(slug, project_id, type_id)
        if issue_type.is_epic:
            return Response(
                {"error": "The epic type is managed via epic settings"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = IssueTypeSerializer(issue_type, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(is_epic=False)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def delete(self, request, slug, project_id, type_id):
        issue_type = self.get_type(slug, project_id, type_id)
        if issue_type.is_epic:
            return Response(
                {"error": "The epic type is managed via epic settings"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Issue.objects.filter(type=issue_type).exists():
            return Response(
                {"error": "This type is in use — deactivate it instead"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        issue_type.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IssuePropertiesEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, type_id):
        issue_type = project_issue_types(slug, project_id).get(pk=type_id)
        properties = issue_type.properties.filter(deleted_at__isnull=True)
        return Response(IssuePropertySerializer(properties, many=True).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def post(self, request, slug, project_id, type_id):
        issue_type = project_issue_types(slug, project_id).get(pk=type_id)
        serializer = IssuePropertySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        prop = serializer.save(issue_type=issue_type, workspace=issue_type.workspace)
        return Response(IssuePropertySerializer(prop).data, status=status.HTTP_201_CREATED)


class IssuePropertyDetailEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN])
    def patch(self, request, slug, project_id, property_id):
        prop = scoped_property(slug, project_id, property_id)
        serializer = IssuePropertySerializer(prop, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def delete(self, request, slug, project_id, property_id):
        prop = scoped_property(slug, project_id, property_id)
        prop.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IssuePropertyOptionsEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, property_id):
        prop = scoped_property(slug, project_id, property_id)
        options = prop.options.filter(deleted_at__isnull=True)
        return Response(IssuePropertyOptionSerializer(options, many=True).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def post(self, request, slug, project_id, property_id):
        prop = scoped_property(slug, project_id, property_id)
        if prop.property_type not in (PropertyTypeChoices.SELECT, PropertyTypeChoices.MULTI_SELECT):
            return Response(
                {"error": "Options are only valid for select properties"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = IssuePropertyOptionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        option = serializer.save(property=prop, workspace=prop.workspace)
        return Response(IssuePropertyOptionSerializer(option).data, status=status.HTTP_201_CREATED)


class IssuePropertyOptionDetailEndpoint(BaseAPIView):
    def get_option(self, slug, project_id, property_id, option_id):
        return IssuePropertyOption.objects.get(
            pk=option_id,
            property_id=property_id,
            workspace__slug=slug,
            property__issue_type__project_issue_types__project_id=project_id,
        )

    @allow_permission([ROLE.ADMIN])
    def patch(self, request, slug, project_id, property_id, option_id):
        option = self.get_option(slug, project_id, property_id, option_id)
        serializer = IssuePropertyOptionSerializer(option, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def delete(self, request, slug, project_id, property_id, option_id):
        option = self.get_option(slug, project_id, property_id, option_id)
        option.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def serialize_value_row(row):
    prop_type = row.property.property_type
    if prop_type == PropertyTypeChoices.NUMBER:
        return str(row.value_number.normalize()) if row.value_number is not None else ""
    if prop_type == PropertyTypeChoices.BOOLEAN:
        return "true" if row.value_boolean else "false"
    if prop_type == PropertyTypeChoices.DATE:
        return row.value_date.isoformat() if row.value_date else ""
    if prop_type in (PropertyTypeChoices.SELECT, PropertyTypeChoices.MULTI_SELECT):
        return str(row.value_option_id) if row.value_option_id else ""
    if prop_type == PropertyTypeChoices.MEMBER:
        return str(row.value_member_id) if row.value_member_id else ""
    return row.value_text or ""


class IssuePropertyValuesEndpoint(BaseAPIView):
    """Bundle read/write of an issue's property values.

    Shape: { "<property_id>": ["<value>", ...], ... } — string-encoded, the
    contract the web issue-modal provider expects.
    """

    def get_issue(self, slug, project_id, issue_id):
        return Issue.objects.get(workspace__slug=slug, project_id=project_id, pk=issue_id)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, issue_id):
        issue = self.get_issue(slug, project_id, issue_id)
        rows = IssuePropertyValue.objects.filter(
            issue=issue,
            property__issue_type_id=issue.type_id,
            property__is_active=True,
            property__deleted_at__isnull=True,
        ).select_related("property")
        values = {}
        for row in rows:
            values.setdefault(str(row.property_id), []).append(serialize_value_row(row))
        return Response(values, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id, issue_id):
        issue = self.get_issue(slug, project_id, issue_id)
        payload = request.data or {}
        if not isinstance(payload, dict):
            return Response({"error": "Expected a property→values map"}, status=status.HTTP_400_BAD_REQUEST)

        # A property is writable only when it belongs to this issue's type.
        # Project-level scoping alone would let clients attach values from a
        # different type and create data that no issue UI can interpret.
        writable = {
            str(prop.id): prop
            for prop in IssueProperty.objects.filter(
                workspace__slug=slug,
                issue_type__project_issue_types__project_id=project_id,
                issue_type_id=issue.type_id,
                is_active=True,
                deleted_at__isnull=True,
            )
        }

        unknown = [key for key in payload.keys() if key not in writable]
        if unknown:
            return Response({"error": f"Unknown properties: {unknown}"}, status=status.HTTP_400_BAD_REQUEST)

        missing_required = [
            prop.display_name
            for key, prop in writable.items()
            if prop.is_required
            and (
                key not in payload
                or not isinstance(payload[key], list)
                or not any(v not in (None, "") for v in payload[key])
            )
        ]
        if missing_required:
            return Response(
                {"error": f"Required properties missing: {missing_required}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Serialize bundle replacement for this issue. Without a row lock,
            # concurrent requests can both delete then insert scalar rows;
            # scalar/multi cardinality cannot be expressed as one DB constraint.
            Issue.objects.select_for_update().get(pk=issue.pk)
            IssuePropertyValue.objects.filter(issue=issue).exclude(property__issue_type_id=issue.type_id).delete()
            for key, raw_values in payload.items():
                prop = writable[key]
                rows = validate_property_values(prop, raw_values, project_id)
                IssuePropertyValue.objects.filter(issue=issue, property=prop).delete()
                IssuePropertyValue.objects.bulk_create(
                    IssuePropertyValue(
                        issue=issue,
                        property=prop,
                        project_id=project_id,
                        workspace=issue.workspace,
                        **row,
                    )
                    for row in rows
                )
        return Response(status=status.HTTP_204_NO_CONTENT)
