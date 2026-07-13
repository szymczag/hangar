# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json
import os
import re
import secrets
from urllib.parse import urlsplit

import requests

# Django imports
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


# Module imports
from plane.license.models import Instance, InstanceEdition
from plane.utils.url_security import pinned_fetch

MAX_RELEASE_RESPONSE_BYTES = 64 * 1024
RELEASE_CHECK_URL_ENV = "HANGAR_RELEASE_CHECK_URL"
DEFAULT_PRODUCT_VERSION = "v0.1.0"
PRODUCT_VERSION_PATTERN_TEXT = (
    r"v"
    r"(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)"
    r"(?:-(?:alpha|beta|rc)\.(?:[1-9][0-9]*))?"
)
PRODUCT_VERSION_PATTERN = re.compile(rf"^{PRODUCT_VERSION_PATTERN_TEXT}$")
HANGAR_RELEASE_TAG_PATTERN = re.compile(rf"^hangar-(?P<version>{PRODUCT_VERSION_PATTERN_TEXT})$")


def normalize_product_version(value):
    if not isinstance(value, str):
        return None
    if PRODUCT_VERSION_PATTERN.fullmatch(value):
        return value
    prefixed_value = f"v{value}"
    if PRODUCT_VERSION_PATTERN.fullmatch(prefixed_value):
        return prefixed_value
    return None


def normalize_hangar_release_tag(value):
    if not isinstance(value, str) or value != value.strip() or len(value) > 255:
        return None
    match = HANGAR_RELEASE_TAG_PATTERN.fullmatch(value)
    return match.group("version") if match is not None else None


class Command(BaseCommand):
    help = "Check if instance in registered else register"

    def add_arguments(self, parser):
        # Positional argument
        parser.add_argument("machine_signature", type=str, help="Machine signature")

    def check_for_current_version(self):
        app_version = normalize_product_version(os.environ.get("APP_VERSION"))
        if app_version is not None:
            return app_version

        try:
            with open("package.json", "r") as file:
                data = json.load(file)
                return normalize_product_version(data.get("version")) or DEFAULT_PRODUCT_VERSION
        except Exception:
            self.stdout.write("Error checking for current version")
            return DEFAULT_PRODUCT_VERSION

    def check_for_latest_version(self, fallback_version):
        release_check_url = os.environ.get(RELEASE_CHECK_URL_ENV, "").strip()
        if not release_check_url:
            return fallback_version

        try:
            parsed = urlsplit(release_check_url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.fragment
            ):
                raise ValueError("Release check URL must be a credential-free HTTPS URL")

            response = pinned_fetch(
                "GET",
                release_check_url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "hangar-release-check",
                },
                timeout=10,
                stream=True,
            )
            try:
                if 300 <= response.status_code < 400:
                    raise requests.RequestException("Release check redirects are not allowed")
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_content(chunk_size=8192):
                    body.extend(chunk)
                    if len(body) > MAX_RELEASE_RESPONSE_BYTES:
                        raise ValueError("Release response exceeds the size limit")
                data = json.loads(body.decode("utf-8"))
            finally:
                response.close()

            if not isinstance(data, dict):
                raise ValueError("Release response must be a JSON object")
            release_version = normalize_hangar_release_tag(data.get("tag_name"))
            if release_version is None:
                raise ValueError("Release response contains an invalid Hangar tag name")
            return release_version
        except (OSError, UnicodeError, ValueError, requests.RequestException, json.JSONDecodeError):
            self.stdout.write("Error checking for latest version")
            return fallback_version

    def handle(self, *args, **options):
        # Check if the instance is registered
        instance = Instance.objects.first()

        current_version = self.check_for_current_version()
        latest_version = self.check_for_latest_version(current_version)

        # If instance is None then register this instance
        if instance is None:
            machine_signature = options.get("machine_signature", "machine-signature")

            if not machine_signature:
                raise CommandError("Machine signature is required")

            instance = Instance.objects.create(
                instance_name="Hangar",
                instance_id=secrets.token_hex(12),
                current_version=current_version,
                latest_version=latest_version,
                last_checked_at=timezone.now(),
                is_test=os.environ.get("IS_TEST", "0") == "1",
                is_telemetry_enabled=False,
                edition=InstanceEdition.PLANE_COMMUNITY.value,
            )

            self.stdout.write(self.style.SUCCESS("Instance registered"))
        else:
            self.stdout.write(self.style.SUCCESS("Instance already registered"))

            # Update the instance details
            instance.last_checked_at = timezone.now()
            instance.current_version = current_version
            instance.latest_version = latest_version
            instance.is_test = os.environ.get("IS_TEST", "0") == "1"
            instance.edition = InstanceEdition.PLANE_COMMUNITY.value
            instance.save()

        return
