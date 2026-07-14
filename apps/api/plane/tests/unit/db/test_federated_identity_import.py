# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import csv
import json
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError

from plane.db.models import FederatedIdentity, FederatedIdentityImportAudit
from plane.tests.factories import UserFactory


def write_mapping(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["email", "user_id", "subject", "subject_format"])
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.django_db
def test_dry_run_validates_without_writing(tmp_path):
    user = UserFactory()
    mapping = tmp_path / "mappings.csv"
    report = tmp_path / "report.json"
    write_mapping(
        mapping,
        [{"email": user.email, "user_id": "", "subject": "employee-123", "subject_format": "employeeId"}],
    )

    call_command(
        "import_federated_identities",
        provider="saml",
        issuer="https://idp.example.test",
        file=mapping,
        report=report,
        dry_run=True,
        stdout=StringIO(),
    )

    assert FederatedIdentity.objects.count() == 0
    assert FederatedIdentityImportAudit.objects.count() == 0
    assert json.loads(report.read_text())["imported_count"] == 1


@pytest.mark.django_db
def test_import_is_idempotent_and_audited(tmp_path):
    user = UserFactory()
    mapping = tmp_path / "mappings.csv"
    write_mapping(
        mapping,
        [{"email": "", "user_id": user.id, "subject": "employee-123", "subject_format": "employeeId"}],
    )

    options = {
        "provider": "saml",
        "issuer": "https://idp.example.test",
        "file": mapping,
        "stdout": StringIO(),
    }
    call_command("import_federated_identities", **options)
    call_command("import_federated_identities", **options)

    identity = FederatedIdentity.objects.get()
    assert identity.user == user
    assert identity.subject == "employee-123"
    audits = list(FederatedIdentityImportAudit.objects.order_by("created_at"))
    assert len(audits) == 2
    assert audits[0].imported_count == 1
    assert audits[1].existing_count == 1

    identity.subject = "changed-subject"
    with pytest.raises(ValidationError, match="immutable"):
        identity.save()


@pytest.mark.django_db
def test_conflicting_duplicate_subject_rolls_back(tmp_path):
    first_user = UserFactory(username="first-import-user")
    second_user = UserFactory(username="second-import-user")
    mapping = tmp_path / "mappings.csv"
    report = tmp_path / "report.json"
    write_mapping(
        mapping,
        [
            {
                "email": first_user.email,
                "user_id": "",
                "subject": "duplicate-subject",
                "subject_format": "employeeId",
            },
            {
                "email": second_user.email,
                "user_id": "",
                "subject": "duplicate-subject",
                "subject_format": "employeeId",
            },
        ],
    )

    with pytest.raises(CommandError, match="validation failed"):
        call_command(
            "import_federated_identities",
            provider="saml",
            issuer="https://idp.example.test",
            file=mapping,
            report=report,
            stdout=StringIO(),
        )

    assert FederatedIdentity.objects.count() == 0
    assert FederatedIdentityImportAudit.objects.count() == 0
    assert json.loads(report.read_text())["errors"][0]["code"] == "DUPLICATE_SUBJECT"
