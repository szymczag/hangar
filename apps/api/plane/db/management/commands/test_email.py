# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.core.management import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.utils.html import strip_tags

# Module imports
from plane.db.models import User
from plane.mailer.service import enqueue_rendered_email


class Command(BaseCommand):
    """Django command to pause execution until db is available"""

    def add_arguments(self, parser):
        # Positional argument
        parser.add_argument("to_email", type=str, help="receiver's email")

    def handle(self, *args, **options):
        receiver_email = options.get("to_email")

        if not receiver_email:
            raise CommandError("Receiver email is required")

        # Prepare email details
        subject = "Test email from Hangar"

        html_content = render_to_string("emails/test_email.html")
        text_content = strip_tags(html_content)

        self.stdout.write(self.style.SUCCESS("Trying to send test email..."))

        # Send the email
        try:
            recipient = User.objects.filter(email__iexact=receiver_email).first()
            result = enqueue_rendered_email(
                template_key="diagnostic.test",
                idempotency_key=f"management-test:{uuid.uuid4()}",
                recipient_user=recipient,
                recipient_email=receiver_email,
                subject=subject,
                text_body=text_content,
                html_body=html_content,
            )
            self.stdout.write(self.style.SUCCESS(f"Email accepted for secure delivery ({result.status})"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: Email could not be delivered due to {e}"))
