# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import logging
import os
import uuid
from io import BytesIO

from billiard.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from plane.utils.url_security import pinned_fetch_following_redirects

# Django imports
from django.utils import timezone

from plane.bgtasks.user_activation_email_task import user_activation_email
from plane.authentication.utils.password import is_password_strong

# Module imports
from plane.authentication.services.invitations import active_signup_invitations
from plane.db.models import FileAsset, Profile, User
from plane.license.utils.instance_value import get_configuration_value
from plane.settings.storage import S3Storage
from plane.utils.exception_logger import log_exception
from plane.utils.host import base_host
from plane.utils.ip_address import get_client_ip
from plane.utils.file_asset_upload import (
    UPLOAD_SIGNATURE_BYTES,
    UPLOAD_VALIDATION_VERSION,
    validate_file_content,
    validate_upload_metadata,
)

from .error import AUTHENTICATION_ERROR_CODES, AuthenticationException


class Adapter:
    """Common interface for all auth providers"""

    def __init__(self, request, provider, callback=None):
        self.request = request
        self.provider = provider
        self.callback = callback
        self.token_data = None
        self.user_data = None
        self.external_identity = None
        self.logger = logging.getLogger("plane.authentication")

    def get_user_token(self, data, headers=None):
        raise NotImplementedError

    def get_user_response(self):
        raise NotImplementedError

    def set_token_data(self, data):
        self.token_data = data

    def set_user_data(self, data):
        self.user_data = data

    def set_external_identity(self, identity):
        self.external_identity = identity

    @staticmethod
    def new_username():
        return uuid.uuid4().hex

    def create_update_account(self, user):
        raise NotImplementedError

    def authenticate(self):
        raise NotImplementedError

    def sanitize_email(self, email):
        # Check if email is present
        if not email:
            self.logger.error("Email is not present")
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["INVALID_EMAIL"],
                error_message="INVALID_EMAIL",
                payload={"email": email},
            )

        # Sanitize email
        email = str(email).lower().strip()

        # validate email
        try:
            validate_email(email)
        except ValidationError:
            self.logger.warning("Email validation failed")
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["INVALID_EMAIL"],
                error_message="INVALID_EMAIL",
                payload={"email": email},
            )
        # Return email
        return email

    def validate_password(self, email):
        """Validate password strength"""
        if not is_password_strong(self.code):
            self.logger.warning("Password is not strong enough")
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["PASSWORD_TOO_WEAK"],
                error_message="PASSWORD_TOO_WEAK",
                payload={"email": email},
            )
        return

    def _check_signup(self, email):
        """Check if sign up is enabled or not and raise exception if not enabled"""

        # Get configuration value
        (ENABLE_SIGNUP,) = get_configuration_value(
            [{"key": "ENABLE_SIGNUP", "default": os.environ.get("ENABLE_SIGNUP", "1")}]
        )

        # Check if sign up is disabled and invite is present or not
        if ENABLE_SIGNUP != "0":
            return None

        from django.db import connection

        invitation = active_signup_invitations(
            email,
            for_update=connection.in_atomic_block,
        ).first()
        if invitation is None:
            self.logger.warning("Sign up is disabled and invite is not present")
            # Raise exception
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["SIGNUP_DISABLED"],
                error_message="SIGNUP_DISABLED",
                payload={"email": email},
            )

        return invitation

    def get_avatar_download_headers(self):
        return {}

    def queue_avatar_download(self, avatar_url, user):
        """Mirror an OAuth avatar outside the authentication request."""

        if not avatar_url:
            return
        try:
            from plane.bgtasks.file_asset_task import download_oauth_avatar

            download_oauth_avatar.delay(
                avatar_url=str(avatar_url),
                user_id=str(user.id),
                provider=str(self.provider),
            )
        except Exception as error:
            # Avatar mirroring is optional and must never fail authentication.
            log_exception(error)

    def check_sync_enabled(self):
        """Check if sync is enabled for the provider"""
        provider_config_map = {
            "google": "ENABLE_GOOGLE_SYNC",
            "github": "ENABLE_GITHUB_SYNC",
            "gitlab": "ENABLE_GITLAB_SYNC",
            "gitea": "ENABLE_GITEA_SYNC",
        }
        config_key = provider_config_map.get(self.provider)
        if config_key:
            (enabled,) = get_configuration_value([{"key": config_key, "default": os.environ.get(config_key, "0")}])
            return enabled == "1"
        return False

    def download_and_upload_avatar(self, avatar_url, user):
        """
        Downloads avatar from OAuth provider and uploads to our storage.
        Returns the uploaded file path or None if failed.
        """
        if not avatar_url:
            return None

        storage = None
        filename = None
        try:
            headers = self.get_avatar_download_headers()
            # Download the avatar image over an SSRF-safe client: the avatar URL
            # comes from the OAuth provider's (attacker-influenceable) profile
            # data, so it must not be allowed to reach internal addresses. The
            # connection is pinned to the validated IP (defeats DNS rebinding)
            # and every redirect hop is re-validated, so a public URL cannot
            # bounce the fetch to an internal target — GHSA-cv9p-325g-wmv5 /
            # GHSA-hx79-5pj5-qh42 (avatar hop).
            # stream=True so the body is read incrementally and the size cap
            # below actually bounds memory (without it, requests buffers the
            # whole body before any check runs).
            response, _ = pinned_fetch_following_redirects(
                "GET", avatar_url, headers=headers, timeout=10, max_redirects=5, stream=True
            )
            try:
                response.raise_for_status()

                # Check content length before downloading
                content_length = response.headers.get("Content-Length")
                max_size = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
                if content_length and int(content_length) > max_size:
                    return None

                # Get content type and determine file extension
                content_type = response.headers.get("Content-Type", "image/jpeg").split(";", 1)[0].strip().lower()
                if content_type == "image/jpg":
                    content_type = "image/jpeg"
                extension_map = {
                    "image/jpeg": "jpg",
                    "image/png": "png",
                    "image/gif": "gif",
                    "image/webp": "webp",
                }
                extension = extension_map.get(content_type)

                if not extension:
                    return None

                # Download with size limit
                chunks = []
                total_size = 0
                for chunk in response.iter_content(chunk_size=8192):
                    total_size += len(chunk)
                    if total_size > max_size:
                        return None
                    chunks.append(chunk)
                content = b"".join(chunks)
                file_size = len(content)
            finally:
                response.close()

            # Generate unique filename
            filename = f"{uuid.uuid4().hex}-user-avatar.{extension}"
            metadata = validate_upload_metadata(
                raw_name=filename,
                raw_size=file_size,
                claimed_mime_type=content_type,
                entity_type=FileAsset.EntityTypeContext.USER_AVATAR,
            )
            detected_mime = validate_file_content(
                expected_mime=metadata.mime_type,
                content=content[:UPLOAD_SIGNATURE_BYTES],
            )

            storage = S3Storage(request=self.request)

            # Create file-like object from the size-bounded buffer
            file_obj = BytesIO(content)
            file_obj.seek(0)

            # Upload using boto3 directly
            upload_success = storage.upload_file(
                file_obj=file_obj,
                object_name=filename,
                content_type=metadata.mime_type,
            )
            if not upload_success:
                return None

            # Get storage metadata
            storage_metadata = storage.get_object_metadata(object_name=filename)
            stored_content_type = ((storage_metadata or {}).get("ContentType") or "").split(";", 1)[0].strip().lower()
            if (
                storage_metadata is None
                or storage_metadata.get("ContentLength") != metadata.size
                or stored_content_type != metadata.mime_type
            ):
                storage.delete_files([filename])
                return None
            storage_metadata.update(
                {
                    "DetectedContentType": detected_mime,
                    "ValidatedAt": timezone.now().isoformat(),
                    "ValidationVersion": UPLOAD_VALIDATION_VERSION,
                }
            )

            # Create FileAsset record
            file_asset = FileAsset.objects.create(
                attributes={
                    "name": f"{self.provider}-avatar.{extension}",
                    "type": metadata.mime_type,
                    "size": metadata.size,
                },
                asset=filename,
                size=metadata.size,
                user=user,
                created_by=user,
                entity_type=FileAsset.EntityTypeContext.USER_AVATAR,
                is_uploaded=True,
                upload_validation_version=UPLOAD_VALIDATION_VERSION,
                storage_metadata=storage_metadata,
            )

            return file_asset

        except SoftTimeLimitExceeded:
            if storage is not None and filename is not None:
                storage.delete_files([filename])
            raise
        except Exception as e:
            if storage is not None and filename is not None:
                storage.delete_files([filename])
            log_exception(e)
            # Return None if upload fails, so original URL can be used as fallback
            return None

    def save_user_data(self, user):
        # Update user details
        user.last_login_medium = self.provider
        user.last_active = timezone.now()
        user.last_login_time = timezone.now()
        user.last_login_ip = get_client_ip(request=self.request)
        user.last_login_uagent = self.request.META.get("HTTP_USER_AGENT")
        user.token_updated_at = timezone.now()
        # Activate provisioned accounts that have never been deactivated.
        # Explicitly-deactivated accounts are rejected earlier in
        # complete_login_or_signup() before this method is ever reached.
        # Save first so activation is persisted before the email side-effect fires.
        was_inactive = not user.is_active
        user.is_active = True
        user.save()
        if was_inactive:
            from django.db import transaction

            def send_activation_email():
                try:
                    user_activation_email.delay(base_host(request=self.request), user.id)
                except Exception as e:
                    log_exception(e)

            transaction.on_commit(send_activation_email)
        return user

    def delete_old_avatar(self, user):
        """Delete the old avatar if it exists"""
        try:
            if user.avatar_asset:
                asset = FileAsset.objects.get(pk=user.avatar_asset_id)
                storage = S3Storage(request=self.request)
                if not storage.delete_files(object_names=[asset.asset.name]):
                    return False

                # Delete the user avatar
                asset.delete()
                user.avatar_asset = None
                user.avatar = ""
                user.save()
            return True
        except FileAsset.DoesNotExist:
            return True
        except Exception as e:
            log_exception(e)
            return False

    def sync_user_data(self, user):
        # Update user details
        first_name = self.user_data.get("user", {}).get("first_name", "")
        last_name = self.user_data.get("user", {}).get("last_name", "")
        user.first_name = first_name if first_name else ""
        user.last_name = last_name if last_name else ""

        # Get email
        email = self.user_data.get("email")

        # Get display name
        display_name = self.user_data.get("user", {}).get("display_name")
        # If display name is not provided, generate a random display name
        if not display_name:
            display_name = User.get_display_name(email)

        # Set display name
        user.display_name = display_name

        # Persist the remote fallback immediately; mirroring is queued after the
        # authentication flow has saved its final user state.
        avatar = self.user_data.get("user", {}).get("avatar", "")
        # Delete the old avatar if it exists
        self.delete_old_avatar(user=user)
        user.avatar = avatar
        user.save()
        return user

    def complete_login_or_signup(self):
        if self.external_identity is not None:
            from plane.authentication.services.federated_auth import authenticate_external_identity

            return authenticate_external_identity(self).user

        # Get email
        email = self.user_data.get("email")

        # Sanitize email
        email = self.sanitize_email(email)

        # Check if the user is present
        user = User.objects.filter(email=email).first()

        # Reject explicitly-deactivated accounts (GHSA-rmmf-rj2q-3rrg).
        # The deactivation endpoint always sets last_logout_time, so using it
        # as the discriminator is more reliable than last_login_time: a
        # provisioned account that was never deactivated has last_logout_time=None
        # and is allowed through for its first login; an account deactivated via
        # the API has last_logout_time set and is blocked regardless of whether
        # it had previously logged in.
        if user and not user.is_active and user.last_logout_time is not None:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["USER_ACCOUNT_DEACTIVATED"],
                error_message="USER_ACCOUNT_DEACTIVATED",
                payload={"email": email},
            )

        # Reject bot service accounts (BOT_USER_LOGIN_FORBIDDEN). Bots (is_bot=True,
        # e.g. the WORKSPACE_SEED bot) are internal identities that act only through
        # API tokens; they must never be assumable via the interactive login/signup
        # flow (email/password, magic code, or any OAuth provider). A brand-new
        # signup can never be a bot — bots are provisioned internally, never through
        # this path — so guarding on an existing `user` record is sufficient.
        if user and user.is_bot:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["BOT_USER_LOGIN_FORBIDDEN"],
                error_message="BOT_USER_LOGIN_FORBIDDEN",
                payload={"email": email},
            )

        # True = new user (signup), False = returning user (login)
        is_signup = not bool(user)
        # If user is not present, create a new user
        if not user:
            # New user
            self._check_signup(email)

            # Initialize user
            user = User(email=email, username=uuid.uuid4().hex)

            # Check if password is autoset
            if self.user_data.get("user").get("is_password_autoset"):
                user.set_password(uuid.uuid4().hex)
                user.is_password_autoset = True
                user.is_email_verified = True

            # Validate password
            else:
                # Validate password
                self.validate_password(email)
                # Set password
                user.set_password(self.code)
                user.is_password_autoset = False

            # Set user details
            first_name = self.user_data.get("user", {}).get("first_name", "")
            last_name = self.user_data.get("user", {}).get("last_name", "")
            user.first_name = first_name if first_name else ""
            user.last_name = last_name if last_name else ""

            user.save()

            # Use the provider URL as an immediate fallback. Mirroring happens
            # asynchronously after the authentication flow finishes.
            avatar = self.user_data.get("user", {}).get("avatar", "")
            if avatar:
                user.avatar = avatar

            # Create profile
            Profile.objects.create(user=user)

        # Check if IDP sync is enabled and user is not signing up
        if self.check_sync_enabled() and not is_signup:
            user = self.sync_user_data(user=user)

        # Save user data
        user = self.save_user_data(user=user)
        avatar = self.user_data.get("user", {}).get("avatar", "")
        if avatar and (is_signup or self.check_sync_enabled()):
            self.queue_avatar_download(avatar_url=avatar, user=user)

        # Call callback if present
        if self.callback:
            self.callback(user, is_signup, self.request)

        # Create or update account if token data is present
        if self.token_data:
            self.create_update_account(user=user)

        # Return user
        return user
