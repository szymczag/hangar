# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Copying a work item's inline images, against a real object store.

Every other storage test in this repository mocks `S3Storage`, and a mock cannot
answer the question this feature exists for: after a project is duplicated, can
somebody who is a member of the copy but **not** of the source actually read the
images in it? Before this was fixed the answer was no, and no mocked test could
have told the difference -- the copy reported success either way.

So this one puts real bytes in the store, runs the real copy, and reads the
result back through a client built independently of the code under test.
"""

import uuid

import pytest

from plane.db.models import (
    FileAsset,
    Issue,
    Project,
    ProjectMember,
    State,
    User,
    Workspace,
    WorkspaceMember,
)
from plane.ext.models import ProjectCopyJob
from plane.ext.services.issue_types import ensure_project_system_types
from plane.ext.services.project_copy import duplicate_project
from plane.ext.tasks import copy_project_work_items
from plane.utils.file_asset_permissions import can_read_file_asset
from plane.utils.file_asset_upload import UPLOAD_VALIDATION_VERSION

ADMIN = 20
MEMBER = 15

# The smallest thing that is genuinely a PNG: the validator derives the MIME type
# from the extension and checks it against the claimed one, so this has to be a
# real image rather than arbitrary bytes.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6360000002000100"
    "05fe02fea7c9"
    "0000000049454e44ae426082"
)


@pytest.fixture
def scenario(db, object_store):
    """A project whose one work item has an image in its description."""
    client, bucket, prefix = object_store
    tag = uuid.uuid4().hex[:8]

    owner = User.objects.create(email=f"owner-{tag}@corp.example", username=uuid.uuid4().hex)
    outsider = User.objects.create(email=f"outsider-{tag}@corp.example", username=uuid.uuid4().hex)

    workspace = Workspace.objects.create(name=f"ws{tag}", slug=f"ws{tag}", owner=owner)
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=ADMIN)
    WorkspaceMember.objects.create(workspace=workspace, member=outsider, role=MEMBER)

    source = Project.objects.create(
        name=f"Source {tag}", identifier=f"S{tag[:4]}".upper(), workspace=workspace, created_by=owner
    )
    ProjectMember.objects.create(project=source, member=owner, workspace=workspace, role=ADMIN)
    ensure_project_system_types(source)
    State.objects.create(
        name="Backlog", color="#000", group="backlog", project=source, workspace=workspace, sequence=1000
    )

    key = f"{prefix}diagram.png"
    client.put_object(Bucket=bucket, Key=key, Body=PNG, ContentType="image/png")

    issue = Issue.objects.create(name="Has an image", project=source, workspace=workspace, created_by=owner)
    asset = FileAsset.objects.create(
        attributes={"name": "diagram.png", "type": "image/png", "size": len(PNG)},
        asset=key,
        size=len(PNG),
        entity_type=FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
        issue=issue,
        project=source,
        workspace=workspace,
        created_by=owner,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
    )
    Issue.objects.filter(pk=issue.pk).update(
        description_html=f'<p>spec</p><image-component src="{asset.id}"></image-component>'
    )

    return {
        "client": client,
        "bucket": bucket,
        "workspace": workspace,
        "owner": owner,
        "outsider": outsider,
        "source": source,
        "asset": asset,
    }


def _duplicate_and_run(scenario):
    result = duplicate_project(source=scenario["source"], actor=scenario["owner"], options={"work_items": True})
    job = ProjectCopyJob.objects.get(target_project=result.project)
    copy_project_work_items(str(job.id))
    job.refresh_from_db()
    return result.project, job


@pytest.mark.storage
@pytest.mark.django_db
def test_a_copied_image_is_a_real_object_in_the_copy(scenario):
    """The bytes are copied, not merely the row.

    `duplicate_file_asset` heads the destination after copying and deletes it if
    it does not match, so a mocked storage layer will happily report success for
    an object that was never written. Reading the bytes back through a separate
    client is the only assertion that distinguishes the two.
    """
    copy, job = _duplicate_and_run(scenario)

    assert job.status in (ProjectCopyJob.Status.COMPLETED, ProjectCopyJob.Status.COMPLETED_WITH_ERRORS), job.reason

    copied_issue = Issue.objects.get(project=copy, name="Has an image")
    assert str(scenario["asset"].id) not in copied_issue.description_html, (
        "the copy must not still reference the source project's asset"
    )

    duplicated = FileAsset.objects.filter(project=copy, entity_type="ISSUE_DESCRIPTION")
    assert duplicated.count() == 1
    new_asset = duplicated.first()
    assert str(new_asset.id) in copied_issue.description_html
    assert new_asset.issue_id == copied_issue.id
    assert new_asset.asset.name != scenario["asset"].asset.name, "a copy, not a second row over the same object"

    stored = scenario["client"].get_object(Bucket=scenario["bucket"], Key=new_asset.asset.name)["Body"].read()
    assert stored == PNG

    # The source is untouched: this copies, it does not move.
    original = scenario["client"].get_object(Bucket=scenario["bucket"], Key=scenario["asset"].asset.name)["Body"].read()
    assert original == PNG


@pytest.mark.storage
@pytest.mark.django_db
def test_a_member_of_the_copy_can_read_its_images_without_joining_the_source(scenario):
    """The behaviour the whole fix exists for.

    Before it, every image in a copied project was a request that only members of
    the *source* could satisfy -- which is precisely the people least likely to be
    looking at the copy.
    """
    copy, _ = _duplicate_and_run(scenario)
    new_asset = FileAsset.objects.get(project=copy, entity_type="ISSUE_DESCRIPTION")

    outsider = scenario["outsider"]
    ProjectMember.objects.create(project=copy, member=outsider, workspace=scenario["workspace"], role=MEMBER)

    assert can_read_file_asset(user_id=outsider.id, asset=new_asset) is True
    # And the copy did not hand them the source's assets on the way.
    assert can_read_file_asset(user_id=outsider.id, asset=scenario["asset"]) is False
