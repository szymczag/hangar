# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from dataclasses import dataclass, field
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES, AuthenticationException
from plane.db.models import Account, FederatedIdentity, Profile, User
from plane.db.models.federated_identity import federated_binding_key


@dataclass(frozen=True)
class ExternalIdentity:
    provider: str
    issuer: str
    subject: str
    subject_format: str
    email: str
    email_verified: bool
    first_name: str = ""
    last_name: str = ""
    avatar_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    legacy_provider_account_id: str = ""


@dataclass(frozen=True)
class FederatedAuthenticationResult:
    user: User
    identity: FederatedIdentity
    is_signup: bool


def _auth_error(code: str, _email: str) -> AuthenticationException:
    return AuthenticationException(
        error_code=AUTHENTICATION_ERROR_CODES[code],
        error_message=code,
        payload={},
    )


def _assert_identity_matches(stored: FederatedIdentity, presented: ExternalIdentity, email: str) -> None:
    if (
        stored.provider != presented.provider
        or stored.issuer != presented.issuer
        or stored.subject_format != presented.subject_format
        or stored.subject != presented.subject
    ):
        raise _auth_error("FEDERATED_IDENTITY_CONFLICT", email)


def _create_user(adapter, external: ExternalIdentity, email: str) -> User:
    user = User(
        email=email,
        username=adapter.new_username(),
        first_name=external.first_name,
        last_name=external.last_name,
        is_password_autoset=True,
        is_email_verified=True,
    )
    user.set_unusable_password()
    user.save()
    Profile.objects.create(user=user)
    return user


def _create_identity(external: ExternalIdentity, user: User, email: str) -> FederatedIdentity:
    return FederatedIdentity.objects.create(
        user=user,
        provider=external.provider,
        issuer=external.issuer,
        subject_format=external.subject_format,
        subject=external.subject,
        email_at_link=email,
        last_email=email,
        last_authenticated_at=timezone.now(),
        metadata=external.metadata,
    )


def authenticate_external_identity(adapter) -> FederatedAuthenticationResult:
    external = adapter.external_identity
    if external is None or not external.provider or not external.issuer or not external.subject:
        raise _auth_error("FEDERATED_IDENTITY_INVALID", "")
    if external.email_verified is not True:
        raise _auth_error("FEDERATED_IDENTITY_INVALID", external.email)

    email = adapter.sanitize_email(external.email)
    binding_key = federated_binding_key(
        external.provider,
        external.issuer,
        external.subject_format,
        external.subject,
    )
    sync_existing = adapter.check_sync_enabled()

    try:
        with transaction.atomic():
            identity = (
                FederatedIdentity.objects.select_for_update()
                .select_related("user")
                .filter(binding_key=binding_key)
                .first()
            )
            signup_invite = None
            is_signup = False

            if identity is not None:
                _assert_identity_matches(identity, external, email)
                user = User.objects.select_for_update().get(pk=identity.user_id)
            else:
                legacy_account = None
                if external.legacy_provider_account_id:
                    legacy_account = (
                        Account.objects.select_for_update()
                        .select_related("user")
                        .filter(
                            provider=external.provider,
                            provider_account_id=external.legacy_provider_account_id,
                        )
                        .first()
                    )

                if legacy_account is not None:
                    user = User.objects.select_for_update().get(pk=legacy_account.user_id)
                    identity = _create_identity(external, user, email)
                    if legacy_account.identity_id not in (None, identity.id):
                        raise _auth_error("FEDERATED_IDENTITY_CONFLICT", email)
                    legacy_account.identity = identity
                    legacy_account.save(update_fields=["identity"])
                else:
                    existing_user = User.objects.select_for_update().filter(email=email).first()
                    if existing_user is not None:
                        raise _auth_error("SSO_ACCOUNT_LINK_REQUIRED", email)
                    signup_invite = adapter._check_signup(email)
                    user = _create_user(adapter, external, email)
                    identity = _create_identity(external, user, email)
                    is_signup = True

                # A concurrent transaction can win the unique binding race.
                # The outer IntegrityError handler fails closed and rolls back
                # every user/invitation/account side effect from this attempt.

            if not user.is_active and user.last_logout_time is not None:
                raise _auth_error("USER_ACCOUNT_DEACTIVATED", email)
            if user.is_bot:
                raise _auth_error("BOT_USER_LOGIN_FORBIDDEN", email)

            adapter.save_user_data(user)

            if adapter.token_data:
                adapter.create_update_account(user=user, identity=identity)

            if adapter.callback:
                adapter.callback(user, is_signup, adapter.request)

            if signup_invite is not None:
                signup_invite.signup_authorized_at = timezone.now()
                signup_invite.save(update_fields=["signup_authorized_at", "updated_at"])

            identity.last_email = email
            identity.last_authenticated_at = timezone.now()
            identity.metadata = {**identity.metadata, **external.metadata}
            identity.save(update_fields=["last_email", "last_authenticated_at", "metadata", "updated_at"])
    except IntegrityError as exc:
        adapter.logger.warning(
            "Federated identity persistence conflict",
            extra={"provider": external.provider, "binding_key": binding_key},
        )
        raise _auth_error("FEDERATED_IDENTITY_CONFLICT", email) from exc

    # Profile synchronization and remote avatar I/O are deliberately outside
    # the identity transaction. Their failure must not alter account binding.
    if sync_existing and not is_signup:
        adapter.sync_user_data(user)
    elif is_signup and external.avatar_url:
        avatar_asset = adapter.download_and_upload_avatar(external.avatar_url, user)
        if avatar_asset:
            user.avatar_asset = avatar_asset
        else:
            user.avatar = external.avatar_url
        user.save(update_fields=["avatar", "avatar_asset", "updated_at"])

    return FederatedAuthenticationResult(user=user, identity=identity, is_signup=is_signup)
