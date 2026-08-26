# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Administrator control over a person's OpenPGP key.

An organisation escrowing keys needs to set the certificate its people's mail is
encrypted to and stop them replacing it. Stated plainly, that is the power to
arrange to read someone's mail: a key set here is trusted without the challenge
that normally proves the holder controls the private half, because the
administrator is vouching for it instead.

That is legitimate with an escrow, and unacceptable if it happens quietly, so
every action writes an immutable record naming who did it, and the account owner
is emailed. Neither is optional.

Mounted under /api/instances/ because the session middleware selects the admin
cookie by that substring in the path, and gated by InstanceAdminPermission, which
requires the WebAuthn second factor.
"""

# Django imports
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.views.base import BaseAPIView
from plane.app.views.user.email_security import _send_key_changed_alert
from plane.authentication.session import BaseSessionAuthentication
from plane.db.models import User, UserOpenPGPKey
from plane.ext.models import OpenPGPAdminAction, UserOpenPGPPolicy
from plane.license.api.permissions import InstanceAdminPermission
from plane.mailer.enums import OpenPGPKeyStatus
from plane.mailer.exceptions import OpenPGPError
from plane.mailer.openpgp import inspect_certificate

# One message for every certificate problem, so this is not an oracle for
# probing what a certificate contains.
CERTIFICATE_ERROR = "The public certificate could not be accepted."


def _error(message: str, response_status=status.HTTP_400_BAD_REQUEST) -> Response:
    return Response({"error": message}, status=response_status)


def _state(user) -> dict:
    policy = UserOpenPGPPolicy.objects.filter(user=user).first()
    active = UserOpenPGPKey.objects.filter(user=user, status=OpenPGPKeyStatus.ACTIVE).first()
    return {
        "user_id": str(user.id),
        "email": user.email,
        "is_locked": bool(policy and policy.is_locked),
        "locked_at": policy.locked_at if policy else None,
        "note": policy.note if policy else "",
        "active_key": None
        if active is None
        else {
            "primary_fingerprint": active.primary_fingerprint,
            "encryption_algorithm": active.encryption_algorithm,
            "key_expires_at": active.key_expires_at,
            "verified_at": active.verified_at,
        },
    }


class InstanceUserOpenPGPEndpoint(BaseAPIView):
    """Read, set, lock and unlock the key an account's mail is encrypted to."""

    authentication_classes = [BaseSessionAuthentication]
    permission_classes = [InstanceAdminPermission]

    def get(self, request, user_id):
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return _error("No such account.", status.HTTP_404_NOT_FOUND)
        return Response(_state(user), status=status.HTTP_200_OK)

    @method_decorator(csrf_protect)
    def post(self, request, user_id):
        """Set the certificate this account's mail is encrypted to."""
        user = User.objects.filter(pk=user_id, is_bot=False).first()
        if user is None:
            return _error("No such account.", status.HTTP_404_NOT_FOUND)

        certificate = request.data.get("certificate") or ""
        note = (request.data.get("note") or "").strip()
        if not certificate.strip():
            return _error("Attach the account holder's public certificate.")

        try:
            info = inspect_certificate(certificate)
        except OpenPGPError:
            return _error(CERTIFICATE_ERROR)

        now = timezone.now()
        with transaction.atomic():
            existing = UserOpenPGPKey.objects.select_for_update().filter(user=user)
            if existing.filter(
                primary_fingerprint=info.primary_fingerprint,
                status=OpenPGPKeyStatus.ACTIVE,
            ).exists():
                return _error("This certificate is already active for the account.", status.HTTP_409_CONFLICT)

            next_version = (existing.count() or 0) + 1
            existing.filter(status__in=[OpenPGPKeyStatus.ACTIVE, OpenPGPKeyStatus.PENDING]).update(
                status=OpenPGPKeyStatus.REPLACED,
                replaced_at=now,
                updated_at=now,
            )
            # Active without a challenge: the challenge proves the holder
            # controls the private key, and here the administrator vouches for
            # it instead. That substitution is the whole risk, which is why the
            # record below is written in the same transaction.
            key = UserOpenPGPKey.objects.create(
                user=user,
                version=next_version,
                certificate=info.normalized_certificate,
                primary_fingerprint=info.primary_fingerprint,
                encryption_subkey_fingerprint=info.encryption_subkey_fingerprint,
                primary_algorithm=info.primary_algorithm,
                encryption_algorithm=info.encryption_algorithm,
                encryption_key_size=info.encryption_key_size,
                key_created_at=info.created_at,
                key_expires_at=info.expires_at,
                last_validated_at=now,
                verified_at=now,
                status=OpenPGPKeyStatus.ACTIVE,
            )
            OpenPGPAdminAction.objects.create(
                subject=user,
                actor=request.user,
                action=OpenPGPAdminAction.Action.KEY_SET,
                primary_fingerprint=info.primary_fingerprint,
                note=note,
            )

        # Outside the transaction: the owner learning of this must not be able
        # to roll it back, and a mail failure must not lose the audit record.
        _send_key_changed_alert(user, "set by an administrator", key.id)
        return Response(_state(user), status=status.HTTP_200_OK)

    @method_decorator(csrf_protect)
    def patch(self, request, user_id):
        """Lock or unlock self-service for this account."""
        user = User.objects.filter(pk=user_id, is_bot=False).first()
        if user is None:
            return _error("No such account.", status.HTTP_404_NOT_FOUND)

        raw = request.data.get("is_locked")
        if not isinstance(raw, bool):
            return _error("Say whether self-service should be locked.")
        note = (request.data.get("note") or "").strip()

        with transaction.atomic():
            policy, _ = UserOpenPGPPolicy.objects.get_or_create(user=user)
            policy.is_locked = raw
            policy.note = note
            policy.locked_by = request.user if raw else None
            policy.locked_at = timezone.now() if raw else None
            policy.save(update_fields=["is_locked", "note", "locked_by", "locked_at", "updated_at"])

            OpenPGPAdminAction.objects.create(
                subject=user,
                actor=request.user,
                action=(OpenPGPAdminAction.Action.LOCKED if raw else OpenPGPAdminAction.Action.UNLOCKED),
                note=note,
            )

        return Response(_state(user), status=status.HTTP_200_OK)
