# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
from datetime import timedelta

# Third party imports
from celery import shared_task
from django.db import OperationalError

# Django imports
# Third party imports
from django.template.loader import render_to_string

# Module imports
from plane.db.models import User
from plane.mailer.service import enqueue_rendered_email
from plane.mailer.tokens import email_idempotency_token
from plane.utils.email import generate_plain_text_from_html
from plane.utils.exception_logger import log_exception


@shared_task(autoretry_for=(OperationalError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def forgot_password(first_name, email, uidb64, token, current_site):
    try:
        relative_link = f"/accounts/reset-password/?uidb64={uidb64}&token={token}&email={email}"
        abs_url = str(current_site) + relative_link

        subject = "Reset your Hangar password"

        context = {
            "first_name": first_name,
            "forgot_password_url": abs_url,
            "email": email,
        }

        html_content = render_to_string("emails/auth/forgot_password.html", context)

        text_content = generate_plain_text_from_html(html_content)

        recipient = User.objects.filter(email__iexact=email).first()
        enqueue_rendered_email(
            recipient_email=email,
            recipient_user=recipient,
            template_key="auth.forgot_password",
            subject=subject,
            text_body=text_content,
            html_body=html_content,
            expires_in=timedelta(hours=1),
            idempotency_key=f"forgot-password:{email_idempotency_token('forgot-password', uidb64, token)}",
        )
        return
    except Exception as e:
        log_exception(e)
        if isinstance(e, OperationalError):
            raise
        return
