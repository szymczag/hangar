# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Asset URLs are served inline only for allow-listed image types, with the response
Content-Type pinned to that type. Any other type, or a missing type, is served as an
attachment typed application/octet-stream.

Fork: the static route (avatars, covers, logos) is public and always inline, so it
answers 404 for anything that is not a server-validated raster image rather than
handing out a download.
"""

from unittest import mock

import pytest
from rest_framework.test import APIClient

from plane.db.models import DeployBoard, FileAsset, Project
from plane.utils.file_asset_upload import UPLOAD_VALIDATION_VERSION


def _avatar(workspace, user, attributes):
    return FileAsset.objects.create(
        attributes=attributes,
        asset=f"{workspace.id}/avatar",
        size=10,
        workspace=workspace,
        user=user,
        created_by=user,
        entity_type=FileAsset.EntityTypeContext.USER_AVATAR,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
    )


def _get_static(asset):
    with mock.patch("plane.settings.storage.boto3") as mock_boto3:
        s3_client = mock_boto3.client.return_value
        s3_client.generate_presigned_url.return_value = "https://signed.example/avatar"
        response = APIClient().get(f"/api/assets/v2/static/{asset.id}/")
    return response, s3_client


@pytest.mark.contract
@pytest.mark.django_db
def test_static_raster_image_is_inline_with_its_type_pinned(workspace, create_user):
    asset = _avatar(workspace, create_user, {"name": "a.png", "type": "image/png", "size": 10})

    response, s3_client = _get_static(asset)

    assert response.status_code == 302
    params = s3_client.generate_presigned_url.call_args.kwargs["Params"]
    assert params["ResponseContentDisposition"].split(";")[0] == "inline"
    assert params["ResponseContentType"] == "image/png"


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("claimed_type", ["image/svg+xml", "text/html", None, 123])
def test_static_route_never_serves_other_types(workspace, create_user, claimed_type):
    attributes = {"name": "a.png", "size": 10}
    if claimed_type is not None:
        attributes["type"] = claimed_type
    asset = _avatar(workspace, create_user, attributes)

    response, s3_client = _get_static(asset)

    assert response.status_code == 404
    s3_client.generate_presigned_url.assert_not_called()


@pytest.mark.contract
@pytest.mark.django_db
def test_static_asset_with_a_non_string_name_still_redirects(workspace, create_user):
    asset = _avatar(workspace, create_user, {"name": 123, "type": "image/png", "size": 10})

    response, s3_client = _get_static(asset)

    assert response.status_code == 302
    params = s3_client.generate_presigned_url.call_args.kwargs["Params"]
    assert params["ResponseContentDisposition"].startswith("inline; filename*=UTF-8''")


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize(
    "claimed_type, expected_disposition, expected_type",
    [
        ("image/png", "inline", "image/png"),
        ("image/svg+xml", "attachment", "application/octet-stream"),
        (123, "attachment", "application/octet-stream"),
    ],
)
def test_spaces_asset_disposition_follows_allow_list(
    workspace, create_user, claimed_type, expected_disposition, expected_type
):
    project = Project.objects.create(name="Board Project", identifier="BRD", workspace=workspace)
    deploy_board = DeployBoard.objects.create(
        entity_name="project", entity_identifier=project.id, project=project, workspace=workspace
    )
    asset = FileAsset.objects.create(
        attributes={"name": "a.png", "type": claimed_type, "size": 10},
        asset=f"{workspace.id}/description",
        size=10,
        workspace=workspace,
        project=project,
        created_by=create_user,
        entity_type=FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
    )

    with mock.patch("plane.settings.storage.boto3") as mock_boto3:
        s3_client = mock_boto3.client.return_value
        s3_client.generate_presigned_url.return_value = "https://signed.example/description"
        response = APIClient().get(f"/api/public/assets/v2/anchor/{deploy_board.anchor}/{asset.id}/")

    assert response.status_code == 302
    params = s3_client.generate_presigned_url.call_args.kwargs["Params"]
    assert params["ResponseContentDisposition"].split(";")[0] == expected_disposition
    assert params.get("ResponseContentType") == expected_type
