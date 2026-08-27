# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Bring existing objects into line with the forced-private visibility policy.

Turning the policy on in God Mode does this already. This exists for the
instance configured through the environment instead, and for confirming after
the fact that nothing was left behind.
"""

from django.core.management.base import BaseCommand

from plane.utils.visibility_policy import apply_private_visibility, force_private_visibility


class Command(BaseCommand):
    help = "Make every project, page and view private and disable published boards."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Run even though the instance is not configured to force private visibility.",
        )

    def handle(self, *args, **options):
        if not force_private_visibility() and not options["force"]:
            self.stderr.write(
                "This instance does not force private visibility, so nothing was changed. "
                "Turn the policy on first, or pass --force to make everything private anyway."
            )
            return

        changed = apply_private_visibility()
        for name, count in changed.items():
            self.stdout.write(f"{name}: {count}")
        self.stdout.write(self.style.SUCCESS("Existing objects now match the policy."))
