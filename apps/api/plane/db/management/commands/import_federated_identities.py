# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import csv
import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from plane.db.models import FederatedIdentity, FederatedIdentityImportAudit, User
from plane.db.models.federated_identity import federated_binding_key


class Command(BaseCommand):
    help = "Import authoritative federated subject-to-user mappings from CSV"

    def add_arguments(self, parser):
        parser.add_argument(
            "--provider", required=True, choices=[choice[0] for choice in FederatedIdentity.Provider.choices]
        )
        parser.add_argument("--issuer", required=True)
        parser.add_argument("--file", required=True, type=Path)
        parser.add_argument("--report", type=Path)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        provider = options["provider"].strip()
        issuer = options["issuer"].strip()
        source_path = options["file"]
        dry_run = options["dry_run"]

        if not issuer:
            raise CommandError("--issuer must not be empty")

        try:
            source_bytes = source_path.read_bytes()
            decoded = source_bytes.decode("utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise CommandError(f"Unable to read UTF-8 CSV: {exc}") from exc

        reader = csv.DictReader(decoded.splitlines())
        required = {"subject", "subject_format"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise CommandError("CSV must contain subject and subject_format columns")
        if not ({"user_id", "email"} & set(reader.fieldnames)):
            raise CommandError("CSV must contain user_id or email")

        rows = list(reader)
        report = {
            "provider": provider,
            "issuer": issuer,
            "source": source_path.name,
            "input_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "dry_run": dry_run,
            "row_count": len(rows),
            "imported_count": 0,
            "existing_count": 0,
            "errors": [],
        }
        mappings = []
        seen_bindings = {}

        for line_number, row in enumerate(rows, start=2):
            subject = (row.get("subject") or "").strip()
            subject_format = (row.get("subject_format") or "").strip()
            email = (row.get("email") or "").strip().lower()
            user_id = (row.get("user_id") or "").strip()

            if not subject or (provider == FederatedIdentity.Provider.SAML and not subject_format):
                report["errors"].append({"line": line_number, "code": "INVALID_SUBJECT"})
                continue

            binding_key = federated_binding_key(provider, issuer, subject_format, subject)
            if binding_key in seen_bindings:
                report["errors"].append(
                    {"line": line_number, "code": "DUPLICATE_SUBJECT", "first_line": seen_bindings[binding_key]}
                )
                continue
            seen_bindings[binding_key] = line_number

            users = User.objects.all()
            if user_id:
                users = users.filter(pk=user_id)
            if email:
                users = users.filter(email__iexact=email)
            if not user_id and not email:
                report["errors"].append({"line": line_number, "code": "USER_IDENTIFIER_REQUIRED"})
                continue
            user = users.first()
            if user is None:
                report["errors"].append({"line": line_number, "code": "USER_NOT_FOUND"})
                continue

            existing = FederatedIdentity.objects.filter(binding_key=binding_key).first()
            if existing is not None and existing.user_id != user.id:
                report["errors"].append({"line": line_number, "code": "BINDING_OWNED_BY_ANOTHER_USER"})
                continue

            mappings.append(
                {
                    "line": line_number,
                    "user": user,
                    "email": email or user.email,
                    "subject": subject,
                    "subject_format": subject_format,
                    "binding_key": binding_key,
                    "existing": existing is not None,
                }
            )

        if report["errors"]:
            self._write_report(report, options["report"])
            raise CommandError(f"Import validation failed with {len(report['errors'])} error(s)")

        if dry_run:
            report["existing_count"] = sum(mapping["existing"] for mapping in mappings)
            report["imported_count"] = len(mappings) - report["existing_count"]
            self._write_report(report, options["report"])
            self.stdout.write(json.dumps(report, sort_keys=True))
            return

        try:
            with transaction.atomic():
                for mapping in mappings:
                    identity = (
                        FederatedIdentity.objects.select_for_update().filter(binding_key=mapping["binding_key"]).first()
                    )
                    if identity is not None:
                        if identity.user_id != mapping["user"].id:
                            raise CommandError(f"Binding conflict at line {mapping['line']}")
                        report["existing_count"] += 1
                        continue
                    FederatedIdentity.objects.create(
                        user=mapping["user"],
                        provider=provider,
                        issuer=issuer,
                        subject_format=mapping["subject_format"],
                        subject=mapping["subject"],
                        email_at_link=mapping["email"],
                        last_email=mapping["email"],
                        metadata={"source": "admin-csv-import", "source_line": mapping["line"]},
                    )
                    report["imported_count"] += 1

                FederatedIdentityImportAudit.objects.create(
                    provider=provider,
                    issuer=issuer,
                    input_sha256=report["input_sha256"],
                    source_name=source_path.name,
                    row_count=report["row_count"],
                    imported_count=report["imported_count"],
                    existing_count=report["existing_count"],
                    report=report,
                )
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"Import rolled back: {exc}") from exc

        self._write_report(report, options["report"])
        self.stdout.write(self.style.SUCCESS(json.dumps(report, sort_keys=True)))

    @staticmethod
    def _write_report(report, path):
        if path is None:
            return
        try:
            path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except OSError as exc:
            raise CommandError(f"Unable to write report: {exc}") from exc
