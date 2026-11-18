# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WEB-10023 / SEC-055: the legacy ``FileAssetEndpoint.post`` must not let the
client set identity/state fields (project, issue, entity_type, is_uploaded...).

Hangar refuses such a request outright (400 ``unsupported_legacy_field``) rather
than ignoring the extra fields, and only stores an upload whose entity context
resolves inside the URL workspace.
"""

from unittest import mock
from uuid import uuid4

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from plane.db.models import FileAsset, Project, ProjectMember
from plane.utils.file_asset_upload import UPLOAD_VALIDATION_VERSION

URL = "/api/workspaces/{slug}/file-assets/"
PNG = b"\x89PNG\r\n\x1a\nlegacy-workspace-upload"


def _file(name):
    return SimpleUploadedFile(name, PNG, content_type="image/png")


@pytest.fixture
def other_project(db, workspace, create_user):
    project = Project.objects.create(name="Other", identifier="OT", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
    return project


@pytest.mark.contract
@pytest.mark.django_db
class TestLegacyFileAssetPostReadOnly:
    def test_forged_fields_are_refused(self, session_client, workspace, other_project, create_user):
        other_ws = uuid4()
        before = FileAsset.objects.count()
        with mock.patch("plane.app.views.asset.base.S3Storage") as storage:
            resp = session_client.post(
                URL.format(slug=workspace.slug),
                {
                    "asset": _file("forged.png"),
                    "attributes": json.dumps({"name": "forged.png", "type": "image/png", "size": 1}),
                    "is_uploaded": "true",
                    "entity_type": FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
                    "entity_identifier": str(other_ws),
                    "project": str(other_project.id),
                    "user": str(create_user.id),
                    "is_deleted": "true",
                    "is_archived": "true",
                    "external_id": "x",
                    "external_source": "x",
                    "size": 999999,
                    "storage_metadata": json.dumps({"a": 1}),
                },
                format="multipart",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content
        assert resp.data["code"] == "unsupported_legacy_field"
        storage.return_value.upload_file.assert_not_called()
        assert FileAsset.objects.count() == before

    @pytest.mark.parametrize(
        "field, value",
        [
            ("attributes", json.dumps({"name": "x.png", "type": "image/png", "size": 1})),
            ("is_uploaded", "true"),
            ("project", "PROJECT"),
            ("user", "USER"),
            ("is_deleted", "true"),
            ("size", "999999"),
            ("storage_metadata", json.dumps({"a": 1})),
        ],
    )
    def test_each_forged_field_is_refused_on_an_otherwise_valid_upload(
        self, session_client, workspace, other_project, create_user, field, value
    ):
        value = {"PROJECT": str(other_project.id), "USER": str(create_user.id)}.get(value, value)
        before = FileAsset.objects.count()
        with mock.patch("plane.app.views.asset.base.S3Storage") as storage:
            resp = session_client.post(
                URL.format(slug=workspace.slug),
                {
                    "asset": _file("ok.png"),
                    "entity_type": FileAsset.EntityTypeContext.WORKSPACE_LOGO,
                    "entity_identifier": str(workspace.id),
                    field: value,
                },
                format="multipart",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content
        assert resp.data["code"] == "unsupported_legacy_field"
        storage.return_value.upload_file.assert_not_called()
        assert FileAsset.objects.count() == before

    @mock.patch("plane.utils.file_asset_upload.magic.from_buffer", return_value="image/png")
    def test_normal_upload_works(self, _magic, session_client, workspace):
        with mock.patch("plane.app.views.asset.base.S3Storage") as storage:
            storage.return_value.upload_file.return_value = True
            storage.return_value.get_object_metadata.return_value = {
                "ContentLength": len(PNG),
                "ContentType": "image/png",
            }
            resp = session_client.post(
                URL.format(slug=workspace.slug),
                {
                    "asset": _file("ok.png"),
                    "entity_type": FileAsset.EntityTypeContext.WORKSPACE_LOGO,
                    "entity_identifier": str(workspace.id),
                },
                format="multipart",
            )
        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        fa = FileAsset.objects.get(id=resp.data["id"])
        assert fa.workspace_id == workspace.id
        assert fa.project_id is None
        assert fa.attributes["name"] == "ok.png"
        assert fa.size == len(PNG) and fa.is_uploaded is True
        assert fa.upload_validation_version == UPLOAD_VALIDATION_VERSION
