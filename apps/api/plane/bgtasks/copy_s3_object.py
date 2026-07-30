# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import uuid
import base64
import requests
from bs4 import BeautifulSoup

# Django imports
from django.conf import settings
from django.utils import timezone

# Module imports
from plane.db.models import FileAsset, Page, Issue
from plane.utils.exception_logger import log_exception
from plane.settings.storage import S3Storage
from celery import shared_task
from plane.utils.url import normalize_url_path
from plane.utils.file_asset_permissions import can_read_file_asset
from plane.utils.file_asset_upload import (
    UPLOAD_VALIDATION_VERSION,
    UploadError,
    validate_upload_metadata,
)


def get_entity_id_field(entity_type, entity_id):
    entity_mapping = {
        FileAsset.EntityTypeContext.WORKSPACE_LOGO: {"workspace_id": entity_id},
        FileAsset.EntityTypeContext.PROJECT_COVER: {"project_id": entity_id},
        FileAsset.EntityTypeContext.USER_AVATAR: {"user_id": entity_id},
        FileAsset.EntityTypeContext.USER_COVER: {"user_id": entity_id},
        FileAsset.EntityTypeContext.ISSUE_ATTACHMENT: {"issue_id": entity_id},
        FileAsset.EntityTypeContext.ISSUE_DESCRIPTION: {"issue_id": entity_id},
        FileAsset.EntityTypeContext.PAGE_DESCRIPTION: {"page_id": entity_id},
        FileAsset.EntityTypeContext.COMMENT_DESCRIPTION: {"comment_id": entity_id},
        FileAsset.EntityTypeContext.DRAFT_ISSUE_DESCRIPTION: {"draft_issue_id": entity_id},
    }
    return entity_mapping.get(entity_type, {})


def extract_asset_ids(html, tag):
    try:
        soup = BeautifulSoup(html, "html.parser")
        return [tag.get("src") for tag in soup.find_all(tag) if tag.get("src")]
    except Exception as e:
        log_exception(e)
        return []


def replace_asset_ids(html, tag, duplicated_assets):
    try:
        soup = BeautifulSoup(html, "html.parser")
        for mention_tag in soup.find_all(tag):
            for asset in duplicated_assets:
                if mention_tag.get("src") == asset["old_asset_id"]:
                    mention_tag["src"] = asset["new_asset_id"]
        return str(soup)
    except Exception as e:
        log_exception(e)
        return html


def update_description(entity, duplicated_assets, tag):
    updated_html = replace_asset_ids(entity.description_html, tag, duplicated_assets)
    entity.description_html = updated_html
    entity.save()
    return updated_html


# Get the description binary and description from the live server
def sync_with_external_service(entity_name, description_html):
    try:
        data = {
            "description_html": description_html,
            "variant": "rich" if entity_name == "PAGE" else "document",
        }

        live_url = settings.LIVE_URL
        if not live_url:
            return {}

        url = normalize_url_path(f"{live_url}/convert-document/")

        response = requests.post(url, json=data, headers=None)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException as e:
        log_exception(e)
    return {}


def copy_assets(entity, entity_identifier, project_id, asset_ids, user_id):
    duplicated_assets = []
    workspace = entity.workspace
    storage = S3Storage()
    expected_entity_type = (
        FileAsset.EntityTypeContext.PAGE_DESCRIPTION
        if isinstance(entity, Page)
        else FileAsset.EntityTypeContext.ISSUE_DESCRIPTION
    )
    original_assets = FileAsset.objects.filter(
        workspace=workspace,
        project_id=project_id,
        id__in=asset_ids,
        entity_type=expected_entity_type,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
    )

    for original_asset in original_assets:
        if not can_read_file_asset(user_id=user_id, asset=original_asset):
            continue
        try:
            metadata = validate_upload_metadata(
                raw_name=(original_asset.attributes or {}).get("name"),
                raw_size=original_asset.size,
                claimed_mime_type=(original_asset.attributes or {}).get("type"),
                entity_type=expected_entity_type,
            )
        except UploadError:
            continue
        source_metadata = storage.get_object_metadata(original_asset.asset.name)
        source_etag = (source_metadata or {}).get("ETag")
        if not source_etag:
            continue

        destination_key = f"{workspace.id}/{uuid.uuid4().hex}-{metadata.name}"
        copied = storage.copy_object(
            original_asset.asset.name,
            destination_key,
            source_etag=source_etag,
            content_type=metadata.mime_type,
        )
        final_metadata = storage.get_object_metadata(destination_key) if copied else None
        final_type = ((final_metadata or {}).get("ContentType") or "").split(";", 1)[0].strip().lower()
        if (
            final_metadata is None
            or final_metadata.get("ContentLength") != metadata.size
            or final_type != metadata.mime_type
        ):
            storage.delete_files([destination_key])
            continue
        try:
            duplicated_asset = FileAsset.objects.create(
                attributes={
                    "name": metadata.name,
                    "type": metadata.mime_type,
                    "size": metadata.size,
                },
                asset=destination_key,
                size=metadata.size,
                workspace=workspace,
                created_by_id=user_id,
                entity_type=expected_entity_type,
                project_id=project_id,
                storage_metadata={
                    **final_metadata,
                    "DetectedContentType": (original_asset.storage_metadata or {}).get(
                        "DetectedContentType",
                        metadata.mime_type,
                    ),
                    "ValidatedAt": timezone.now().isoformat(),
                    "ValidationVersion": UPLOAD_VALIDATION_VERSION,
                    "ValidationSource": "validated-description-copy",
                },
                is_uploaded=True,
                upload_validation_version=UPLOAD_VALIDATION_VERSION,
                **get_entity_id_field(expected_entity_type, entity_identifier),
            )
        except Exception:
            storage.delete_files([destination_key])
            raise
        duplicated_assets.append(
            {
                "new_asset_id": str(duplicated_asset.id),
                "old_asset_id": str(original_asset.id),
            }
        )
    return duplicated_assets


@shared_task
def copy_s3_objects_of_description_and_assets(entity_name, entity_identifier, project_id, slug, user_id):
    """
    Step 1: Extract asset ids from the description_html of the entity
    Step 2: Duplicate the assets
    Step 3: Update the description_html of the entity with the new asset ids (change the src of img tag)
    Step 4: Request the live server to generate the description_binary and description for the entity

    """
    try:
        model_class = {"PAGE": Page, "ISSUE": Issue}.get(entity_name)
        if not model_class:
            raise ValueError(f"Unsupported entity_name: {entity_name}")

        entity = model_class.objects.get(id=entity_identifier)
        asset_ids = extract_asset_ids(entity.description_html, "image-component")

        duplicated_assets = copy_assets(entity, entity_identifier, project_id, asset_ids, user_id)

        updated_html = update_description(entity, duplicated_assets, "image-component")

        external_data = sync_with_external_service(entity_name, updated_html)

        if external_data:
            entity.description_json = external_data.get("description_json")
            entity.description_binary = base64.b64decode(external_data.get("description_binary"))
            entity.save()

        return
    except Exception as e:
        log_exception(e)
        return []
