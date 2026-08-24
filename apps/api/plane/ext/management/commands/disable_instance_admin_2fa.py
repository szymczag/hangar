# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Recovery for an administrator who lost their security key.

The only way back in when the second factor is unavailable, so it has to work on
an instance that is otherwise unwell: it never enqueues Celery work and never
depends on the console being reachable.
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from plane.db.models import Session, User
from plane.ext.models import InstanceAdminWebAuthnChallenge, InstanceAdminWebAuthnCredential
from plane.license.models import InstanceAdmin

logger = logging.getLogger("plane.security")


class Command(BaseCommand):
    help = "Remove an instance administrator's WebAuthn credentials so they can enroll again"

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--list", action="store_true", help="Show the credentials and exit")
        parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
        parser.add_argument(
            "--keep-sessions",
            action="store_true",
            help="Leave the administrator's live console sessions alone",
        )

    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            raise CommandError(f"No user with email {email}")

        # Not a general-purpose key wiper: it only applies to the console.
        if not InstanceAdmin.objects.filter(user=user).exists():
            raise CommandError(f"{email} is not an instance administrator")

        credentials = InstanceAdminWebAuthnCredential.objects.filter(user=user)
        if options["list"]:
            if not credentials.exists():
                self.stdout.write("No credentials registered.")
                return
            for item in credentials:
                last_used = f"{item.last_used_at:%Y-%m-%d}" if item.last_used_at else "never"
                self.stdout.write(
                    f"{item.id}  {item.nickname!r}  aaguid={item.aaguid or '-'}  "
                    f"created={item.created_at:%Y-%m-%d}  last_used={last_used}"
                )
            return

        count = credentials.count()
        if count == 0:
            self.stdout.write("No credentials to remove; the administrator will enroll at next sign-in.")
            return

        if not options["yes"]:
            self.stdout.write(f"About to remove {count} credential(s) for {email}:")
            for item in credentials:
                self.stdout.write(f"  {item.nickname!r} ({item.id})")
            if input("Type 'yes' to continue: ").strip().lower() != "yes":
                raise CommandError("Aborted.")

        # queryset.update, not instance.delete(): SoftDeleteModel.delete()
        # dispatches a Celery task, and a recovery command has to work when the
        # broker is down.
        credentials.update(deleted_at=timezone.now())
        InstanceAdminWebAuthnChallenge.objects.filter(user=user).delete()

        cleared = 0
        if not options["keep_sessions"]:
            # If the key was lost with the laptop, leaving the thief's live
            # session alive would defeat the point of resetting it.
            for session in Session.objects.filter(user_id=str(user.id)):
                session.delete()
                cleared += 1

        logger.warning("Instance admin 2FA reset for %s (%s credentials, %s sessions)", email, count, cleared)
        self.stdout.write(
            self.style.SUCCESS(
                f"Removed {count} credential(s) and {cleared} session(s). "
                f"{email} must enroll a new security key at their next sign-in."
            )
        )
