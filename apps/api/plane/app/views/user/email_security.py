"""Self-service OpenPGP key lifecycle endpoints."""

import hmac
import logging
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from plane.app.serializers.email_security import (
    OpenPGPChallengeVerifySerializer,
    OpenPGPKeyRemovalSerializer,
    OpenPGPKeySerializer,
    OpenPGPKeyUploadSerializer,
)
from plane.app.views.base import BaseAPIView
from plane.db.models import EmailOutbox, EmailSuppression, OpenPGPKeyChallenge, User, UserOpenPGPKey
from plane.mailer.audit import email_receipt
from plane.mailer.crypto import encrypt_bytes, keyed_digest
from plane.mailer.enums import OpenPGPKeyStatus, OutboxStatus
from plane.mailer.exceptions import MailerError, OpenPGPError
from plane.mailer.openpgp import inspect_certificate
from plane.mailer.service import enqueue_rendered_email

logger = logging.getLogger("plane.api")
REAUTHENTICATION_WINDOW = timedelta(minutes=15)
CHALLENGE_LIFETIME = timedelta(minutes=15)
MAX_CHALLENGE_ATTEMPTS = 5
CHALLENGE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


class OpenPGPUploadThrottle(UserRateThrottle):
    rate = "5/hour"
    scope = "openpgp_upload"


class OpenPGPChallengeThrottle(UserRateThrottle):
    rate = "5/hour"
    scope = "openpgp_challenge"


class OpenPGPVerifyThrottle(UserRateThrottle):
    rate = "20/hour"
    scope = "openpgp_verify"


class OpenPGPTestThrottle(UserRateThrottle):
    rate = "3/hour"
    scope = "openpgp_test"


def _feature_required():
    if not settings.EMAIL_OPENPGP_ENABLED:
        return Response(
            {"error": "OpenPGP email security is not enabled for this instance."},
            status=status.HTTP_409_CONFLICT,
        )
    return None


def _require_recent_authentication(request, password: str = "") -> Response | None:
    user = request.user
    if not user.is_password_autoset:
        if not password or not user.check_password(password):
            return Response(
                {"error": "Your current password is required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        request.session["reauthenticated_at"] = timezone.now().isoformat()
        request.session.save()
        return None

    raw_timestamp = request.session.get("reauthenticated_at")
    parsed = parse_datetime(raw_timestamp) if isinstance(raw_timestamp, str) else None
    if parsed is None or timezone.now() - parsed > REAUTHENTICATION_WINDOW:
        return Response(
            {"error": "Sign in again before changing your email encryption key."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def _send_key_changed_alert(user, action: str, key_id: uuid.UUID) -> None:
    try:
        enqueue_rendered_email(
            recipient_email=user.email,
            recipient_user=user,
            template_key="security.openpgp_changed",
            subject="Hangar email security changed",
            text_body=f"Your OpenPGP email key was {action}. If you did not do this, secure your account now.",
            html_body=(
                f"<p>Your OpenPGP email key was <strong>{action}</strong>.</p>"
                "<p>If you did not do this, secure your account now.</p>"
            ),
            idempotency_key=f"openpgp-key-changed:{key_id}:{action}",
            expires_in=timedelta(hours=24),
        )
    except MailerError:
        logger.exception("Could not enqueue OpenPGP key-change alert", extra={"key_id": str(key_id)})


class EmailSecurityStatusEndpoint(BaseAPIView):
    def get(self, request):
        UserOpenPGPKey.objects.filter(
            user=request.user,
            status__in=[OpenPGPKeyStatus.ACTIVE, OpenPGPKeyStatus.PENDING, OpenPGPKeyStatus.REPLACED],
            key_expires_at__isnull=False,
            key_expires_at__lte=timezone.now(),
        ).update(status=OpenPGPKeyStatus.EXPIRED, updated_at=timezone.now())
        keys = UserOpenPGPKey.objects.filter(user=request.user, status__in=["active", "pending"]).order_by("-version")
        active = next((key for key in keys if key.status == OpenPGPKeyStatus.ACTIVE), None)
        pending = next((key for key in keys if key.status == OpenPGPKeyStatus.PENDING), None)
        email_hash = keyed_digest(request.user.email.strip().lower(), purpose="recipient-email")
        suppressions = list(
            EmailSuppression.objects.filter(email_hash=email_hash, is_active=True).values_list("reason", flat=True)
        )
        return Response(
            {
                "enabled": settings.EMAIL_OPENPGP_ENABLED,
                "notification_mode": "encrypted" if active else "in_app_only",
                "active_key": OpenPGPKeySerializer(active).data if active else None,
                "pending_key": OpenPGPKeySerializer(pending).data if pending else None,
                "account_mail_encrypted": False,
                "active_suppressions": suppressions,
            },
            status=status.HTTP_200_OK,
        )


class EmailSecurityReceiptEndpoint(BaseAPIView):
    def get(self, request):
        email_hash = keyed_digest(request.user.email.strip().lower(), purpose="recipient-email")
        queryset = EmailOutbox.objects.filter(Q(recipient=request.user) | Q(recipient_email_hash=email_hash))
        receipt_code = request.query_params.get("receipt", "").strip().upper()
        if receipt_code:
            queryset = queryset.filter(receipt_code=receipt_code)
        queryset = queryset.order_by("-created_at")[:100]
        return Response(
            {"results": [email_receipt(outbox) for outbox in queryset]},
            status=status.HTTP_200_OK,
        )


class EmailSecurityKeyUploadEndpoint(BaseAPIView):
    throttle_classes = [OpenPGPUploadThrottle]

    def post(self, request):
        disabled = _feature_required()
        if disabled:
            return disabled
        serializer = OpenPGPKeyUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reauth_error = _require_recent_authentication(request, serializer.validated_data.get("password", ""))
        if reauth_error:
            return reauth_error
        try:
            info = inspect_certificate(serializer.validated_data["certificate"])
        except OpenPGPError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        key_id = uuid.uuid4()
        now = timezone.now()
        with transaction.atomic():
            User.objects.select_for_update().get(pk=request.user.pk)
            existing = UserOpenPGPKey.objects.select_for_update().filter(user=request.user)
            if existing.filter(
                primary_fingerprint=info.primary_fingerprint,
                status__in=[OpenPGPKeyStatus.ACTIVE, OpenPGPKeyStatus.PENDING],
            ).exists():
                return Response(
                    {"error": "This public certificate is already configured."},
                    status=status.HTTP_409_CONFLICT,
                )
            existing.filter(status=OpenPGPKeyStatus.PENDING).update(
                status=OpenPGPKeyStatus.INVALID,
                updated_at=now,
            )
            next_version = (existing.aggregate(value=Max("version"))["value"] or 0) + 1
            key = UserOpenPGPKey.objects.create(
                id=key_id,
                user=request.user,
                version=next_version,
                certificate_ciphertext=encrypt_bytes(
                    info.normalized_certificate.encode("utf-8"),
                    associated_data=f"openpgp-certificate:{key_id}".encode(),
                ),
                primary_fingerprint=info.primary_fingerprint,
                encryption_subkey_fingerprint=info.encryption_subkey_fingerprint,
                primary_algorithm=info.primary_algorithm,
                encryption_algorithm=info.encryption_algorithm,
                encryption_key_size=info.encryption_key_size,
                key_created_at=info.created_at,
                key_expires_at=info.expires_at,
                last_validated_at=now,
                status=OpenPGPKeyStatus.PENDING,
            )
        return Response(OpenPGPKeySerializer(key).data, status=status.HTTP_201_CREATED)


class EmailSecurityChallengeEndpoint(BaseAPIView):
    throttle_classes = [OpenPGPChallengeThrottle]

    def post(self, request, key_id):
        disabled = _feature_required()
        if disabled:
            return disabled
        key = (
            UserOpenPGPKey.objects.filter(
                pk=key_id,
                user=request.user,
                status=OpenPGPKeyStatus.PENDING,
            )
            .filter(Q(key_expires_at__isnull=True) | Q(key_expires_at__gt=timezone.now()))
            .first()
        )
        if key is None:
            return Response({"error": "Pending key not found."}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        challenge_id = uuid.uuid4()
        code = "".join(secrets.choice(CHALLENGE_ALPHABET) for _ in range(16))
        with transaction.atomic():
            OpenPGPKeyChallenge.objects.filter(key=key, consumed_at__isnull=True).update(consumed_at=now)
            challenge = OpenPGPKeyChallenge.objects.create(
                id=challenge_id,
                key=key,
                token_digest=keyed_digest(code, purpose=f"openpgp-challenge:{challenge_id}"),
                expires_at=now + CHALLENGE_LIFETIME,
            )
        try:
            result = enqueue_rendered_email(
                recipient_email=request.user.email,
                recipient_user=request.user,
                template_key="security.openpgp_challenge",
                subject="Verify your Hangar OpenPGP key",
                text_body=f"Enter this verification code in Hangar: {code}",
                html_body=f"<p>Enter this verification code in Hangar:</p><p><strong>{code}</strong></p>",
                idempotency_key=f"openpgp-challenge:{challenge.id}",
                expires_in=CHALLENGE_LIFETIME,
                encryption_key=key,
            )
        except MailerError:
            challenge.consumed_at = timezone.now()
            challenge.save(update_fields=("consumed_at", "updated_at"))
            return Response(
                {"error": "The encrypted verification message could not be queued."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if result.status not in {
            OutboxStatus.QUEUED,
            OutboxStatus.PROCESSING,
            OutboxStatus.ACCEPTED,
            OutboxStatus.ACCEPTANCE_UNKNOWN,
            OutboxStatus.DELIVERED,
        }:
            challenge.consumed_at = timezone.now()
            challenge.save(update_fields=("consumed_at", "updated_at"))
            return Response(
                {"error": "Email delivery is suppressed for this address."},
                status=status.HTTP_409_CONFLICT,
            )
        challenge.sent_at = timezone.now()
        challenge.save(update_fields=("sent_at", "updated_at"))
        return Response(
            {"challenge_id": challenge.id, "expires_at": challenge.expires_at},
            status=status.HTTP_202_ACCEPTED,
        )


class EmailSecurityChallengeVerifyEndpoint(BaseAPIView):
    throttle_classes = [OpenPGPVerifyThrottle]

    def post(self, request, key_id):
        disabled = _feature_required()
        if disabled:
            return disabled
        serializer = OpenPGPChallengeVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        now = timezone.now()
        with transaction.atomic():
            challenge = (
                OpenPGPKeyChallenge.objects.select_for_update()
                .select_related("key")
                .filter(
                    key_id=key_id,
                    key__user=request.user,
                    key__status=OpenPGPKeyStatus.PENDING,
                    consumed_at__isnull=True,
                    expires_at__gt=now,
                )
                .order_by("-created_at")
                .first()
            )
            if challenge is None:
                return Response(
                    {"error": "The verification challenge is missing or expired."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            expected = challenge.token_digest
            supplied = keyed_digest(
                serializer.validated_data["code"].upper(),
                purpose=f"openpgp-challenge:{challenge.id}",
            )
            if not hmac.compare_digest(expected, supplied):
                challenge.attempts += 1
                if challenge.attempts >= MAX_CHALLENGE_ATTEMPTS:
                    challenge.consumed_at = now
                challenge.save(update_fields=("attempts", "consumed_at", "updated_at"))
                return Response({"error": "The verification code is invalid."}, status=status.HTTP_400_BAD_REQUEST)

            key = UserOpenPGPKey.objects.select_for_update().get(pk=key_id, user=request.user)
            if key.key_expires_at is not None and key.key_expires_at <= now:
                key.status = OpenPGPKeyStatus.EXPIRED
                key.save(update_fields=("status", "updated_at"))
                challenge.consumed_at = now
                challenge.save(update_fields=("consumed_at", "updated_at"))
                return Response(
                    {"error": "The OpenPGP key expired before verification."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            UserOpenPGPKey.objects.filter(user=request.user, status=OpenPGPKeyStatus.ACTIVE).update(
                status=OpenPGPKeyStatus.REPLACED,
                replaced_at=now,
                updated_at=now,
            )
            key.status = OpenPGPKeyStatus.ACTIVE
            key.verified_at = now
            key.last_validated_at = now
            key.save(update_fields=("status", "verified_at", "last_validated_at", "updated_at"))
            challenge.consumed_at = now
            challenge.save(update_fields=("consumed_at", "updated_at"))

        _send_key_changed_alert(request.user, "activated", key.id)
        return Response(OpenPGPKeySerializer(key).data, status=status.HTTP_200_OK)


class EmailSecurityKeyEndpoint(BaseAPIView):
    def delete(self, request, key_id):
        disabled = _feature_required()
        if disabled:
            return disabled
        serializer = OpenPGPKeyRemovalSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        reauth_error = _require_recent_authentication(request, serializer.validated_data.get("password", ""))
        if reauth_error:
            return reauth_error
        now = timezone.now()
        with transaction.atomic():
            key = (
                UserOpenPGPKey.objects.select_for_update()
                .filter(
                    pk=key_id,
                    user=request.user,
                    status__in=[OpenPGPKeyStatus.ACTIVE, OpenPGPKeyStatus.PENDING],
                )
                .first()
            )
            if key is None:
                return Response({"error": "Key not found."}, status=status.HTTP_404_NOT_FOUND)
            key.status = OpenPGPKeyStatus.REVOKED
            key.revoked_at = now
            key.save(update_fields=("status", "revoked_at", "updated_at"))
            OpenPGPKeyChallenge.objects.filter(key=key, consumed_at__isnull=True).update(consumed_at=now)
        _send_key_changed_alert(request.user, "removed", key.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmailSecurityTestEndpoint(BaseAPIView):
    throttle_classes = [OpenPGPTestThrottle]

    def post(self, request, key_id):
        disabled = _feature_required()
        if disabled:
            return disabled
        key = (
            UserOpenPGPKey.objects.filter(
                pk=key_id,
                user=request.user,
                status=OpenPGPKeyStatus.ACTIVE,
            )
            .filter(Q(key_expires_at__isnull=True) | Q(key_expires_at__gt=timezone.now()))
            .first()
        )
        if key is None:
            return Response({"error": "Active key not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            result = enqueue_rendered_email(
                recipient_email=request.user.email,
                recipient_user=request.user,
                template_key="security.openpgp_test",
                subject="Hangar encrypted email test",
                text_body="Your Hangar OpenPGP email configuration works.",
                html_body="<p>Your Hangar OpenPGP email configuration works.</p>",
                idempotency_key=f"openpgp-test:{key.id}:{timezone.now().strftime('%Y%m%d%H')}",
                expires_in=timedelta(hours=1),
                encryption_key=key,
            )
        except MailerError:
            return Response(
                {"error": "The encrypted test message could not be queued."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if result.status not in {
            OutboxStatus.QUEUED,
            OutboxStatus.PROCESSING,
            OutboxStatus.ACCEPTED,
            OutboxStatus.ACCEPTANCE_UNKNOWN,
            OutboxStatus.DELIVERED,
        }:
            return Response(
                {"error": "Email delivery is suppressed for this address."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response({"status": result.status, "outbox_id": result.outbox_id}, status=status.HTTP_202_ACCEPTED)
