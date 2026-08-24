# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from plane.db.models import FederatedIdentity
from plane.ext.services.federated_import import (
    FederatedImportConflict,
    FederatedImportError,
    apply_federated_import,
    plan_federated_import,
)


class Command(BaseCommand):
    """Import authoritative federated subject-to-user mappings from CSV.

    The rules themselves live in plane.ext.services.federated_import, shared
    with the admin console upload. This command is the shell-side wrapper:
    file handling, the report file, and exit status.
    """

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
        source_path = options["file"]
        dry_run = options["dry_run"]

        try:
            source_bytes = source_path.read_bytes()
        except OSError as exc:
            raise CommandError(f"Unable to read {source_path}: {exc}") from exc

        try:
            plan = plan_federated_import(
                provider=options["provider"],
                issuer=options["issuer"],
                source_bytes=source_bytes,
                source_name=source_path.name,
            )
        except FederatedImportError as exc:
            raise CommandError(str(exc)) from exc

        if not plan.is_valid:
            report = plan.as_report(dry_run=dry_run)
            self._write_report(report, options["report"])
            raise CommandError(f"Import validation failed with {len(plan.errors)} error(s)")

        if dry_run:
            report = plan.as_report(dry_run=True)
            self._write_report(report, options["report"])
            self.stdout.write(json.dumps(report, sort_keys=True))
            return

        try:
            report = apply_federated_import(plan)
        except (FederatedImportConflict, FederatedImportError) as exc:
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
