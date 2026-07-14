# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import hashlib
from datetime import timedelta

# Third party imports
from celery import shared_task
from django.db import OperationalError

# Django imports
from django.template.loader import render_to_string

# Module imports
from plane.db.models import User
from plane.mailer.service import enqueue_rendered_email
from plane.utils.email import generate_plain_text_from_html
from plane.utils.exception_logger import log_exception


@shared_task(autoretry_for=(OperationalError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def send_email_update_magic_code(email, token):
    try:
        subject = "Verify your new email address"
        context = {"code": token, "email": email}

        html_content = render_to_string("emails/auth/magic_signin.html", context)
        text_content = generate_plain_text_from_html(html_content)

        recipient = User.objects.filter(email__iexact=email).first()
        enqueue_rendered_email(
            recipient_email=email,
            recipient_user=recipient,
            template_key="account.email_update_code",
            subject=subject,
            text_body=text_content,
            html_body=html_content,
            expires_in=timedelta(minutes=10),
            idempotency_key=f"email-update-code:{hashlib.sha256(f'{email.lower()}:{token}'.encode()).hexdigest()}",
        )
        return
    except Exception as e:
        log_exception(e)
        if isinstance(e, OperationalError):
            raise
        return


@shared_task(autoretry_for=(OperationalError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def send_email_update_confirmation(email, event_id):
    """
    Send a confirmation email to the user after their email address has been successfully updated.

    Args:
        email: The new email address that was successfully updated
    """
    try:
        # Send the confirmation email
        subject = "Hangar email address successfully updated"
        context = {"email": email}

        html_content = render_to_string("emails/user/email_updated.html", context)
        text_content = generate_plain_text_from_html(html_content)

        recipient = User.objects.filter(email__iexact=email).first()
        enqueue_rendered_email(
            recipient_email=email,
            recipient_user=recipient,
            template_key="account.email_updated",
            subject=subject,
            text_body=text_content,
            html_body=html_content,
            idempotency_key=f"email-updated:{event_id}:{hashlib.sha256(email.lower().encode()).hexdigest()}",
        )
        return
    except Exception as e:
        log_exception(e)
        if isinstance(e, OperationalError):
            raise
        return
