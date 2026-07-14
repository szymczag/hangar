"""Instance-administrator email delivery audit and suppression controls."""

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.db.models import EmailOutbox, EmailSuppression
from plane.mailer.audit import email_receipt
from plane.mailer.crypto import keyed_digest

from .base import BaseAPIView


class InstanceEmailDeliveryLogEndpoint(BaseAPIView):
    def get(self, request):
        queryset = EmailOutbox.objects.all().order_by("-created_at")
        recipient = request.query_params.get("recipient", "").strip().lower()
        receipt = request.query_params.get("receipt", "").strip().upper()
        delivery_status = request.query_params.get("status", "").strip()
        if recipient:
            queryset = queryset.filter(recipient_email_hash=keyed_digest(recipient, purpose="recipient-email"))
        if receipt:
            queryset = queryset.filter(receipt_code=receipt)
        if delivery_status:
            queryset = queryset.filter(status=delivery_status)
        try:
            limit = max(1, min(int(request.query_params.get("limit", 100)), 250))
        except ValueError:
            return Response({"error": "limit must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
        rows = list(queryset[:limit])
        counts = dict(EmailOutbox.objects.values_list("status").annotate(total=Count("id")))
        oldest_due = (
            EmailOutbox.objects.filter(
                status__in=["queued", "failed_retryable"],
                next_attempt_at__lte=timezone.now(),
            )
            .order_by("next_attempt_at")
            .values_list("next_attempt_at", flat=True)
            .first()
        )
        return Response(
            {
                "results": [email_receipt(row, admin=True) for row in rows],
                "status_counts": counts,
                "oldest_due_age_seconds": int((timezone.now() - oldest_due).total_seconds()) if oldest_due else 0,
            }
        )


class InstanceEmailSuppressionEndpoint(BaseAPIView):
    def get(self, request):
        rows = EmailSuppression.objects.filter(is_active=True).select_related("recipient").order_by("-created_at")[:250]
        return Response(
            {
                "results": [
                    {
                        "id": row.id,
                        "recipient_user_id": row.recipient_id,
                        "recipient_email": row.recipient.email if row.recipient_id else None,
                        "email_hash": row.email_hash,
                        "reason": row.reason,
                        "source": row.source,
                        "created_at": row.created_at,
                    }
                    for row in rows
                ]
            }
        )

    def post(self, request):
        suppression_id = request.data.get("id")
        reason = str(request.data.get("reason", "")).strip()
        if not suppression_id or len(reason) < 10:
            return Response(
                {"error": "A suppression id and an operator reason of at least 10 characters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            suppression = EmailSuppression.objects.select_for_update().filter(pk=suppression_id).first()
            if suppression is None or not suppression.is_active:
                return Response({"error": "Active suppression not found."}, status=status.HTTP_404_NOT_FOUND)
            suppression.is_active = False
            suppression.deactivated_at = timezone.now()
            suppression.deactivation_reason = reason[:255]
            suppression.updated_by = request.user
            suppression.save(
                update_fields=(
                    "is_active",
                    "deactivated_at",
                    "deactivation_reason",
                    "updated_by",
                    "updated_at",
                )
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
