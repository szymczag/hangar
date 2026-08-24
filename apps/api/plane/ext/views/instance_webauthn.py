# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Second-factor endpoints for the instance-admin console.

These must live under a path containing "instances": the session middleware
selects the admin cookie by that substring (plane/authentication/middleware/
session.py), so a route mounted anywhere else would silently read and write the
*application* session instead.

The pending endpoints answer an anonymous caller, so they carry their own gate
(pending.load) rather than a permission class, and CSRF is applied explicitly —
DRF only enforces it once it has found a logged-in user, which by design has not
happened yet.
"""

# Python imports
import base64
import secrets
from datetime import timedelta

# Django imports
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

# Third party imports
import webauthn
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from webauthn.helpers import options_to_json
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    CredentialDeviceType,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

# Module imports
from plane.app.views.base import BaseAPIView
from plane.authentication.session import BaseSessionAuthentication
from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES, AuthenticationException
from plane.authentication.rate_limit import (
    AdminWebAuthnOptionsThrottle,
    AdminWebAuthnRegisterThrottle,
    AdminWebAuthnVerifyThrottle,
)
from plane.authentication.utils.host import base_host
from plane.authentication.utils.login import user_login
from plane.ext.auth.webauthn import config, pending
from plane.ext.models import InstanceAdminWebAuthnChallenge, InstanceAdminWebAuthnCredential
from plane.license.api.permissions import InstanceAdminPermission
from plane.license.models import InstanceAdmin
from plane.utils.exception_logger import log_exception
from plane.utils.ip_address import get_client_ip


def _b64(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _error(code, http_status=status.HTTP_400_BAD_REQUEST):
    exc = AuthenticationException(error_code=AUTHENTICATION_ERROR_CODES[code], error_message=code)
    return Response(exc.get_error_dict(), status=http_status)


class _WebAuthnBase(BaseAPIView):
    """Shared plumbing.

    AllowAny because the caller is usually mid-sign-in and therefore anonymous;
    each endpoint carries its own gate. Session authentication stays enabled so
    an administrator who *is* signed in can register an additional key — without
    it request.user is permanently anonymous and that path is unreachable, which
    with the last-credential rule would leave no way to rotate a key at all.
    """

    permission_classes = [AllowAny]
    authentication_classes = [BaseSessionAuthentication]

    def _configured(self, request):
        """Refuse early when the browser would reject what we are about to mint."""
        reason = config.validate_config(request)
        if reason is None:
            return None
        log_exception(Exception(f"WebAuthn is misconfigured: {reason}"))
        exc = AuthenticationException(
            error_code=AUTHENTICATION_ERROR_CODES["ADMIN_2FA_NOT_CONFIGURED"],
            error_message="ADMIN_2FA_NOT_CONFIGURED",
            payload={"reason": reason},
        )
        return Response(exc.get_error_dict(), status=status.HTTP_409_CONFLICT)

    def _issue_challenge(self, request, user, purpose):
        # Housekeeping: without this every options request would leave a row
        # behind forever. Scoped to this user, so it stays cheap.
        InstanceAdminWebAuthnChallenge.objects.filter(user=user).filter(
            Q(expires_at__lte=timezone.now()) | Q(consumed_at__isnull=False)
        ).delete()
        raw = secrets.token_bytes(32)
        challenge = _b64(raw)
        InstanceAdminWebAuthnChallenge.objects.create(
            user=user,
            purpose=purpose,
            challenge=challenge,
            session_key=request.session.session_key or "",
            rp_id=config.rp_id(request),
            origin=config.admin_origin(request),
            expires_at=timezone.now() + timedelta(seconds=settings.ADMIN_2FA_CHALLENGE_TTL),
        )
        return raw, challenge

    def _consume_challenge(self, request, user, purpose, challenge):
        """Claim a challenge exactly once, or return None.

        A conditional UPDATE rather than get-then-save: two concurrent verify
        calls would both pass a read-and-check.
        """
        now = timezone.now()
        claimed = InstanceAdminWebAuthnChallenge.objects.filter(
            user=user,
            purpose=purpose,
            challenge=challenge,
            consumed_at__isnull=True,
            expires_at__gt=now,
            session_key=request.session.session_key or "",
        ).update(consumed_at=now)
        if claimed != 1:
            return None
        return InstanceAdminWebAuthnChallenge.objects.filter(challenge=challenge).first()

    def _complete_login(self, request, user, credential=None):
        user.is_active = True
        user.last_active = timezone.now()
        user.last_login_time = timezone.now()
        user.last_login_ip = get_client_ip(request=request)
        user.last_login_uagent = request.META.get("HTTP_USER_AGENT")
        user.token_updated_at = timezone.now()
        user.save()

        user_login(request=request, user=user, is_admin=True)
        pending.mark_verified(request, credential_id=getattr(credential, "id", None))
        return Response(
            {
                "status": "success",
                "redirect_url": base_host(request=request, is_admin=True) + "general/",
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_protect, name="dispatch")
class AdminWebAuthnAuthenticationOptionsEndpoint(_WebAuthnBase):
    throttle_classes = [AdminWebAuthnOptionsThrottle]

    def post(self, request):
        misconfigured = self._configured(request)
        if misconfigured is not None:
            return misconfigured
        try:
            user, _ = pending.load(request, expected_stage=pending.STAGE_ASSERT)
        except pending.PendingError as error:
            return _error(error.code, status.HTTP_409_CONFLICT)

        credentials = InstanceAdminWebAuthnCredential.objects.filter(user=user, disabled_at__isnull=True)
        if not credentials.exists():
            return _error("ADMIN_2FA_ENROLLMENT_REQUIRED", status.HTTP_409_CONFLICT)

        raw, _ = self._issue_challenge(request, user, InstanceAdminWebAuthnChallenge.Purpose.AUTHENTICATION)
        options = webauthn.generate_authentication_options(
            rp_id=config.rp_id(request),
            challenge=raw,
            timeout=60000,
            # Scoped to this administrator: the allow-list is the enumeration
            # boundary, so it must never be built from anything the caller sent.
            allow_credentials=[PublicKeyCredentialDescriptor(id=_unb64(item.credential_id)) for item in credentials],
            user_verification=UserVerificationRequirement.PREFERRED,
        )
        return Response({"options": options_to_json(options)}, status=status.HTTP_200_OK)


@method_decorator(csrf_protect, name="dispatch")
class AdminWebAuthnAuthenticationVerifyEndpoint(_WebAuthnBase):
    throttle_classes = [AdminWebAuthnVerifyThrottle]

    def post(self, request):
        misconfigured = self._configured(request)
        if misconfigured is not None:
            return misconfigured
        try:
            user, _ = pending.load(request, expected_stage=pending.STAGE_ASSERT)
        except pending.PendingError as error:
            return _error(error.code, status.HTTP_409_CONFLICT)

        pending.record_attempt(request)
        payload = request.data.get("credential")
        if not payload:
            return _error("ADMIN_2FA_VERIFICATION_FAILED")

        raw_id = (payload.get("rawId") or payload.get("id") or "").strip()
        credential = InstanceAdminWebAuthnCredential.objects.filter(
            user=user, credential_id=raw_id, disabled_at__isnull=True
        ).first()
        challenge_value = request.data.get("challenge") or ""
        challenge = self._consume_challenge(
            request, user, InstanceAdminWebAuthnChallenge.Purpose.AUTHENTICATION, challenge_value
        )
        # One answer for every cryptographic failure: no oracle separating
        # "unknown credential" from "bad signature".
        if credential is None or challenge is None:
            return _error("ADMIN_2FA_VERIFICATION_FAILED")

        try:
            verification = webauthn.verify_authentication_response(
                credential=payload,
                expected_challenge=_unb64(challenge.challenge),
                expected_rp_id=challenge.rp_id,
                # The snapshot, like expected_rp_id above: a configuration
                # change between issuing and verifying must not produce a
                # mismatched pair.
                expected_origin=challenge.origin,
                credential_public_key=_unb64(credential.public_key),
                # Zero, deliberately: py_webauthn would raise on a regressed
                # counter, which loses the distinction between "this signature
                # is wrong" and "this key has been cloned". We want the second
                # to disable the credential, so the check below is ours.
                credential_current_sign_count=0,
                require_user_verification=False,
            )
        except (InvalidAuthenticationResponse, ValueError, KeyError):
            return _error("ADMIN_2FA_VERIFICATION_FAILED")

        # A counter that goes backwards means the authenticator was cloned.
        # Only meaningful when the device uses counters at all: many report 0
        # forever, and treating 0 <= 0 as a clone would lock those out.
        if credential.sign_count > 0 and verification.new_sign_count <= credential.sign_count:
            credential.disabled_at = timezone.now()
            credential.save(update_fields=["disabled_at", "updated_at"])
            log_exception(Exception(f"WebAuthn signature counter regressed for credential {credential.id}"))
            return _error("ADMIN_2FA_VERIFICATION_FAILED")

        credential.sign_count = verification.new_sign_count
        credential.last_used_at = timezone.now()
        credential.last_used_ip = get_client_ip(request=request) or ""
        credential.last_uv = bool(getattr(verification, "user_verified", False))
        credential.save(update_fields=["sign_count", "last_used_at", "last_used_ip", "last_uv", "updated_at"])

        return self._complete_login(request, user, credential)


def _may_register(request):
    """Either a pending enrollment, or an administrator adding another key.

    Returns (user, error_response). An already-verified administrator may add a
    key without a second password prompt, because the session already proved
    both factors.
    """
    try:
        return pending.load(request, expected_stage=pending.STAGE_ENROLL)[0], None
    except pending.PendingError as error:
        if request.user.is_authenticated and pending.is_verified(request.session):
            if InstanceAdmin.objects.filter(user=request.user).exists():
                return request.user, None
        return None, _error(error.code, status.HTTP_409_CONFLICT)


@method_decorator(csrf_protect, name="dispatch")
class AdminWebAuthnRegistrationOptionsEndpoint(_WebAuthnBase):
    throttle_classes = [AdminWebAuthnRegisterThrottle]

    def post(self, request):
        misconfigured = self._configured(request)
        if misconfigured is not None:
            return misconfigured
        user, error = _may_register(request)
        if error is not None:
            return error

        existing = list(InstanceAdminWebAuthnCredential.objects.filter(user=user))
        # One handle per administrator, reused across their keys. Not the user
        # UUID: that would hand a database identifier to every authenticator.
        handle = existing[0].user_handle if existing else _b64(secrets.token_bytes(32))
        raw, _ = self._issue_challenge(request, user, InstanceAdminWebAuthnChallenge.Purpose.REGISTRATION)

        options = webauthn.generate_registration_options(
            rp_id=config.rp_id(request),
            rp_name=settings.WEBAUTHN_RP_NAME,
            user_id=_unb64(handle),
            user_name=user.email,
            user_display_name=user.display_name or user.email,
            challenge=raw,
            timeout=60000,
            # A second factor, not a passkey: no resident key, so this
            # supplements the password rather than replacing it.
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.DISCOURAGED,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
            exclude_credentials=[PublicKeyCredentialDescriptor(id=_unb64(item.credential_id)) for item in existing],
        )
        return Response(
            {"options": options_to_json(options), "user_handle": handle},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_protect, name="dispatch")
class AdminWebAuthnRegistrationVerifyEndpoint(_WebAuthnBase):
    throttle_classes = [AdminWebAuthnRegisterThrottle]

    def post(self, request):
        misconfigured = self._configured(request)
        if misconfigured is not None:
            return misconfigured
        user, error = _may_register(request)
        if error is not None:
            return error

        payload = request.data.get("credential")
        nickname = (request.data.get("nickname") or "").strip()[:64] or "Security key"
        handle = (request.data.get("user_handle") or "").strip()
        if not payload or not handle:
            return _error("ADMIN_2FA_VERIFICATION_FAILED")

        challenge = self._consume_challenge(
            request, user, InstanceAdminWebAuthnChallenge.Purpose.REGISTRATION, request.data.get("challenge") or ""
        )
        if challenge is None:
            return _error("ADMIN_2FA_VERIFICATION_FAILED")

        try:
            verification = webauthn.verify_registration_response(
                credential=payload,
                expected_challenge=_unb64(challenge.challenge),
                expected_rp_id=challenge.rp_id,
                expected_origin=challenge.origin,
                require_user_verification=False,
            )
        except (InvalidRegistrationResponse, ValueError, KeyError):
            return _error("ADMIN_2FA_VERIFICATION_FAILED")

        credential_id = _b64(verification.credential_id)
        # The unique constraint on credential_id is global, so a key already
        # registered to someone else cannot be claimed here.
        if InstanceAdminWebAuthnCredential.objects.filter(credential_id=credential_id).exists():
            return _error("ADMIN_2FA_VERIFICATION_FAILED")

        credential = InstanceAdminWebAuthnCredential.objects.create(
            user=user,
            credential_id=credential_id,
            public_key=_b64(verification.credential_public_key),
            sign_count=verification.sign_count,
            transports=[t for t in ((payload.get("response") or {}).get("transports") or []) if isinstance(t, str)],
            aaguid=str(getattr(verification, "aaguid", "") or "")[:36],
            user_handle=handle,
            nickname=nickname,
            backup_eligible=getattr(verification, "credential_device_type", None) == CredentialDeviceType.MULTI_DEVICE,
            backup_state=bool(getattr(verification, "credential_backed_up", False)),
        )

        # Enrollment completes the sign-in: the password was proved inside the
        # same bounded window, so a second prompt would buy nothing.
        if pending.peek(request):
            return self._complete_login(request, user, credential)
        return Response({"status": "success", "id": str(credential.id)}, status=status.HTTP_201_CREATED)


class AdminWebAuthnCredentialsEndpoint(BaseAPIView):
    """List and remove registered keys. Requires a fully verified session."""

    permission_classes = [InstanceAdminPermission]

    def get(self, request):
        credentials = InstanceAdminWebAuthnCredential.objects.filter(user=request.user)
        return Response(
            [
                {
                    "id": str(item.id),
                    "nickname": item.nickname,
                    "created_at": item.created_at,
                    "last_used_at": item.last_used_at,
                    "backup_eligible": item.backup_eligible,
                    "disabled_at": item.disabled_at,
                }
                for item in credentials
            ],
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        credential = InstanceAdminWebAuthnCredential.objects.filter(pk=pk, user=request.user).first()
        if credential is None:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # Removing the last key would lock this administrator out at the next
        # sign-in, recoverable only from a shell.
        remaining = InstanceAdminWebAuthnCredential.objects.filter(user=request.user, disabled_at__isnull=True).exclude(
            pk=pk
        )
        if not remaining.exists():
            return _error("ADMIN_2FA_LAST_CREDENTIAL", status.HTTP_409_CONFLICT)

        credential.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
