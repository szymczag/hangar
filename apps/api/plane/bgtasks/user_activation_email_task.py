# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
from django.template.loader import render_to_string

# Third party imports
from celery import shared_task
from django.db import OperationalError

# Module imports
from plane.db.models import User
from plane.mailer.service import enqueue_rendered_email
from plane.utils.email import generate_plain_text_from_html
from plane.utils.exception_logger import log_exception


@shared_task(autoretry_for=(OperationalError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def user_activation_email(current_site, user_id):
    try:
        # Send email to user when account is activated
        user = User.objects.get(id=user_id)
        subject = "Your Hangar account has been activated"

        context = {"email": str(user.email), "profile_url": current_site + "/profile"}

        # Send email to user
        html_content = render_to_string("emails/user/user_activation.html", context)

        text_content = generate_plain_text_from_html(html_content)
        enqueue_rendered_email(
            recipient_email=user.email,
            recipient_user=user,
            template_key="account.activation",
            subject=subject,
            text_body=text_content,
            html_body=html_content,
            idempotency_key=f"account-activation:{user.id}:{user.updated_at.isoformat()}",
        )
        return
    except Exception as e:
        log_exception(e)
        if isinstance(e, OperationalError):
            raise
        return
