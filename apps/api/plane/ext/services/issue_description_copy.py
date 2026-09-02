# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Re-point the images inside a copied work item's description.

A work item's ``description_html`` embeds each inline image as an asset id on an
``<image-component src=...>``. Copying the HTML verbatim therefore leaves every
image in the copy pointing at the *source* project's asset -- which a member of
the copy who is not in the source cannot read, and which breaks outright when the
source is deleted.

The obvious reuse does not work. ``copy_assets`` in
:mod:`plane.bgtasks.copy_s3_object` filters candidate assets by ``project_id``,
which in a cross-project copy is the *target*, so it matches nothing, copies
nothing and reports success. What it does have that is reusable is the HTML
handling and the live-server call, and those are imported here.

``copyable_asset`` is the primitive this hangs on: it resolves an asset *and*
authorises the read against a named actor, with no project filter. Dropping the
project filter is what makes a cross-project copy possible, and that permission
check is what stops it becoming a way to read assets the initiator could not.
"""

from __future__ import annotations

import base64
import logging

from bs4 import BeautifulSoup
from django.utils.html import strip_tags

from plane.bgtasks.copy_s3_object import (
    extract_asset_ids,
    replace_asset_ids,
    sync_with_external_service,
)
from plane.db.models import FileAsset, Issue
from plane.settings.storage import S3Storage
from plane.utils.file_asset_copy import AssetCopyError, copyable_asset, duplicate_file_asset

logger = logging.getLogger(__name__)

# One copy must not pin a worker on object storage, and there is no storage quota
# anywhere in this codebase to stop it doubling a workspace's usage either. This
# cap is the only control.
MAX_ASSET_COPIES = 2000

IMAGE_TAG = "image-component"


def _referenced_ids(html: str) -> list:
    return [asset_id for asset_id in extract_asset_ids(html or "", IMAGE_TAG) if asset_id]


def _already_copied(html: str, target_project_id) -> bool:
    """Whether this item's images already belong to the copy.

    Self-verifying, which is what a resumable pass over object storage needs:
    an S3 copy cannot be rolled back with the database, so the only trustworthy
    answer to "did this already happen" is to look at the result.
    """
    ids = _referenced_ids(html)
    if not ids:
        return True
    owned = FileAsset.objects.filter(id__in=ids, project_id=target_project_id).count()
    return owned == len(set(ids))


def _drop_images(html: str, asset_ids) -> str:
    """Remove the elements for assets that could not be copied.

    Leaving the ``src`` pointing at the source project is worse than losing the
    image: it renders as a broken request for everyone outside that project,
    which looks like the copy is faulty rather than incomplete.
    """
    if not asset_ids:
        return html
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.find_all(IMAGE_TAG):
        if element.get("src") in asset_ids:
            element.decompose()
    return str(soup)


def copy_descriptions(*, job, target_project, ids, tally) -> None:
    """Duplicate the inline images of every copied work item that has any.

    ``ids`` maps source work item id -> copied work item id. Only items whose
    description carries an image are touched, which keeps the live-server round
    trips proportional to images rather than to work items.
    """
    if not ids:
        return

    if job.initiated_by_id is None:
        # `copyable_asset` authorises against this person. Running without one
        # would copy assets nobody was checked against, and there is no safe
        # default -- so the images are left alone and the omission is reported.
        tally.note("work_items:assets-no-initiator")
        return

    storage = S3Storage()
    workspace = target_project.workspace
    copied_assets = 0
    failed_assets = 0
    reconversion_failed = False

    sources = (
        Issue.objects.filter(id__in=list(ids))
        .exclude(description_html__isnull=True)
        .values_list("id", "description_html")
    )

    for source_id, source_html in sources:
        asset_ids = _referenced_ids(source_html)
        if not asset_ids:
            continue

        target_id = ids[source_id]
        target_html = Issue.objects.filter(pk=target_id).values_list("description_html", flat=True).first()
        if _already_copied(target_html, target_project.id):
            continue

        if copied_assets >= MAX_ASSET_COPIES:
            tally.note("work_items:assets-truncated")
            break

        duplicated, unreadable = [], []
        for asset_id in dict.fromkeys(asset_ids):
            original = copyable_asset(asset_id=asset_id, workspace=workspace, actor_id=job.initiated_by_id)
            if original is None:
                unreadable.append(asset_id)
                continue
            try:
                new_asset = duplicate_file_asset(
                    storage=storage,
                    original_asset=original,
                    workspace=workspace,
                    entity_type=FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
                    entity_fields={"issue_id": target_id},
                    project_id=target_project.id,
                    actor_id=job.initiated_by_id,
                )
            except AssetCopyError:
                logger.warning("Could not copy description image %s into project %s", asset_id, target_project.id)
                unreadable.append(asset_id)
                continue
            duplicated.append({"old_asset_id": str(asset_id), "new_asset_id": str(new_asset.id)})
            copied_assets += 1

        updated_html = replace_asset_ids(target_html or "", IMAGE_TAG, duplicated)
        updated_html = _drop_images(updated_html, set(unreadable))
        failed_assets += len(unreadable)

        fields = {
            "description_html": updated_html,
            "description_stripped": strip_tags(updated_html) if updated_html else None,
        }

        # The live server rebuilds the collaborative representation. It is not
        # reachable on every deployment, and returns {} on any failure, so both
        # the empty result and a missing key are guarded -- `b64decode(None)`
        # raises, which is a live fragility in the upstream caller.
        external = sync_with_external_service("ISSUE", updated_html) or {}
        encoded = external.get("description_binary")
        if encoded:
            fields["description_json"] = external.get("description_json") or {}
            fields["description_binary"] = base64.b64decode(encoded)
        else:
            reconversion_failed = True

        # A queryset write, never `save()`: that makes the sequence-allocation
        # branch of `Issue.save()` structurally unreachable rather than merely
        # unreached, so a copied item cannot be handed a second number here.
        Issue.objects.filter(pk=target_id).update(**fields)

    tally.add("description_images", copied_assets)
    if failed_assets:
        tally.add("description_images_dropped", failed_assets)
        tally.note("work_items:assets-not-readable")
    if reconversion_failed:
        tally.note("work_items:descriptions-not-reconverted")
