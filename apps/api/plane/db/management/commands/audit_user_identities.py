# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Report how each user actually signs in.

Needed before pinning a domain to a provider. Accounts at the domain fall into
two groups that behave differently at the cutover — one is adopted on the next
sign-in, the other is refused until its subject is imported — and there is no
way to tell them apart from the user list alone.

Read-only: it never writes, so it is safe to run against production.
"""

import csv
import io

from django.core.management.base import BaseCommand

from plane.db.models import Account, FederatedIdentity, User

STATUS_FEDERATED = "federated"
STATUS_ADOPTABLE = "adoptable"
STATUS_NEEDS_IMPORT = "needs-import"
STATUS_NO_SSO = "password-only"


class Command(BaseCommand):
    help = "Report the sign-in methods and federated bindings held by each user"

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            help="Only report addresses at this domain, e.g. corp.com",
        )
        parser.add_argument(
            "--provider",
            help="Provider a domain is being pinned to, e.g. google. Decides whether an "
            "account counts as adoptable or as needing an import.",
        )
        parser.add_argument("--csv", action="store_true", help="Emit CSV instead of a table")
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Include deactivated accounts, which are excluded by default",
        )

    def handle(self, *args, **options):
        domain = (options.get("domain") or "").strip().lstrip("@").lower()
        provider = (options.get("provider") or "").strip().lower()

        users = User.objects.all().order_by("email")
        if domain:
            users = users.filter(email__iendswith=f"@{domain}")
        if not options["include_inactive"]:
            users = users.filter(is_active=True)
        users = list(users)

        identities = {}
        for identity in FederatedIdentity.objects.filter(user__in=users):
            identities.setdefault(identity.user_id, []).append(identity)

        accounts = {}
        for account in Account.objects.filter(user__in=users):
            accounts.setdefault(account.user_id, set()).add(account.provider)

        rows = []
        for user in users:
            bound = identities.get(user.id, [])
            oauth_providers = sorted(accounts.get(user.id, set()))
            bound_providers = sorted({identity.provider for identity in bound})

            if provider:
                if provider in bound_providers:
                    # Already bound: signs in through this provider today.
                    status = STATUS_FEDERATED
                elif provider in oauth_providers:
                    # A prior OAuth account for the same provider is adopted on
                    # the next sign-in, keeping the user id and memberships.
                    status = STATUS_ADOPTABLE
                else:
                    # Nothing links this account to the provider, so the address
                    # is held by an unlinked user and sign-in will be refused.
                    status = STATUS_NEEDS_IMPORT
            elif bound_providers:
                status = STATUS_FEDERATED
            elif oauth_providers:
                status = STATUS_ADOPTABLE
            else:
                status = STATUS_NO_SSO

            rows.append(
                {
                    "user_id": str(user.id),
                    "email": user.email,
                    "is_active": user.is_active,
                    "has_password": not user.is_password_autoset,
                    "oauth_accounts": ",".join(oauth_providers),
                    "federated_identities": ",".join(f"{identity.provider}:{identity.issuer}" for identity in bound),
                    "status": status,
                }
            )

        if options["csv"]:
            # Rendered into a buffer and written once, so the output goes
            # through the command's stdout wrapper and stays capturable.
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()) if rows else ["email"])
            writer.writeheader()
            writer.writerows(rows)
            self.stdout.write(buffer.getvalue())
            return

        self._render_table(rows, provider)

    def _render_table(self, rows, provider):
        if not rows:
            self.stdout.write("No matching users.")
            return

        width = max(len(row["email"]) for row in rows)
        self.stdout.write(f"{'EMAIL'.ljust(width)}  {'STATUS'.ljust(13)}  PASSWORD  SIGN-IN RECORDS")
        for row in rows:
            records = row["federated_identities"] or row["oauth_accounts"] or "-"
            self.stdout.write(
                f"{row['email'].ljust(width)}  {row['status'].ljust(13)}  "
                f"{'yes' if row['has_password'] else 'no '}       {records}"
            )

        counts = {}
        for row in rows:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        self.stdout.write("")
        self.stdout.write("  ".join(f"{status}={count}" for status, count in sorted(counts.items())))

        needs_import = counts.get(STATUS_NEEDS_IMPORT, 0)
        if provider and needs_import:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    f"{needs_import} account(s) would be refused after pinning this domain to "
                    f"'{provider}'. Collect each one's subject and load it with "
                    f"import_federated_identities before enabling SSO_ENFORCED_DOMAINS."
                )
            )
