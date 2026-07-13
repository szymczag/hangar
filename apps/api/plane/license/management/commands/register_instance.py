# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json
import secrets
import os
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


class Command(BaseCommand):
    help = "Check if instance in registered else register"

    def add_arguments(self, parser):
        # Positional argument
        parser.add_argument("machine_signature", type=str, help="Machine signature")

    def check_for_current_version(self):
        if os.environ.get("APP_VERSION", False):
            return os.environ.get("APP_VERSION")

        try:
            with open("package.json", "r") as file:
                data = json.load(file)
                return data.get("version", "v0.1.0")
        except Exception:
            self.stdout.write("Error checking for current version")
            return "v0.1.0"

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
            tag_name = data.get("tag_name")
            if not isinstance(tag_name, str) or not tag_name.strip() or len(tag_name) > 255:
                raise ValueError("Release response contains an invalid tag name")
            return tag_name.strip()
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
