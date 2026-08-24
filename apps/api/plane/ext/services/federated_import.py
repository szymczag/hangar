# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Plan and apply CSV imports of federated identities.

This decides who may sign in as an existing account, so it is the most
dangerous operation the product exposes: a row naming someone else's address
alongside an attacker's subject hands over that account, and the rightful owner
sees nothing change. It was reachable only from a shell until the console grew
an upload, which is why the rules live here rather than in either caller —
two entry points enforcing two slightly different sets of rules is how the
weaker one becomes the way in.

Validation is all-or-nothing. A file with one bad row imports nothing, because
a partial import leaves an operator reconciling which half applied against a
report they have to read carefully to notice anything went wrong.
"""

import csv
import hashlib
from dataclasses import dataclass, field
from uuid import uuid4

from django.core import signing
from django.db import transaction

from plane.db.models import FederatedIdentity, FederatedIdentityImportAudit, User
from plane.db.models.federated_identity import federated_binding_key

REQUIRED_COLUMNS = frozenset({"subject", "subject_format"})
IDENTIFIER_COLUMNS = frozenset({"user_id", "email"})

# Refusal codes. Every one of them aborts the whole file.
INVALID_SUBJECT = "INVALID_SUBJECT"
DUPLICATE_SUBJECT = "DUPLICATE_SUBJECT"
USER_IDENTIFIER_REQUIRED = "USER_IDENTIFIER_REQUIRED"
USER_NOT_FOUND = "USER_NOT_FOUND"
BINDING_OWNED_BY_ANOTHER_USER = "BINDING_OWNED_BY_ANOTHER_USER"
ACCOUNT_ALREADY_FEDERATED = "ACCOUNT_ALREADY_FEDERATED"


GRANT_SALT = "plane.ext.federated-identity-import.v1"
# Long enough to read a preview carefully, short enough that a grant left in a
# tab is not still spendable after the operator has walked away.
GRANT_TTL_SECONDS = 900


# Why an import was turned away, as a code rather than a sentence. Callers look
# the wording up in REFUSAL_MESSAGES instead of rendering the exception, so no
# exception text — and nothing an exception chained from — can reach a response
# by someone later interpolating a caught error into a message.
FILE_NOT_UTF8 = "FILE_NOT_UTF8"
ISSUER_REQUIRED = "ISSUER_REQUIRED"
UNKNOWN_PROVIDER = "UNKNOWN_PROVIDER"
MISSING_SUBJECT_COLUMNS = "MISSING_SUBJECT_COLUMNS"
MISSING_IDENTIFIER_COLUMN = "MISSING_IDENTIFIER_COLUMN"
PLAN_HAS_REFUSALS = "PLAN_HAS_REFUSALS"

GRANT_MISSING = "GRANT_MISSING"
GRANT_EXPIRED = "GRANT_EXPIRED"
GRANT_INVALID = "GRANT_INVALID"
GRANT_MISMATCH = "GRANT_MISMATCH"

BINDING_TAKEN_SINCE_PREVIEW = "BINDING_TAKEN_SINCE_PREVIEW"
ACCOUNT_FEDERATED_SINCE_PREVIEW = "ACCOUNT_FEDERATED_SINCE_PREVIEW"

REFUSAL_MESSAGES = {
    FILE_NOT_UTF8: "The file must be UTF-8 encoded CSV.",
    ISSUER_REQUIRED: "An issuer is required.",
    UNKNOWN_PROVIDER: "Unknown identity provider.",
    MISSING_SUBJECT_COLUMNS: "The CSV must contain subject and subject_format columns.",
    MISSING_IDENTIFIER_COLUMN: "The CSV must contain a user_id or email column.",
    PLAN_HAS_REFUSALS: "A plan with refusals is never applied.",
    GRANT_MISSING: "Preview the file before confirming the import.",
    GRANT_EXPIRED: "The import preview expired. Preview the file again.",
    GRANT_INVALID: "The import preview is invalid.",
    GRANT_MISMATCH: "This confirmation does not match the file that was previewed.",
    BINDING_TAKEN_SINCE_PREVIEW: "A subject in this file was linked to another account since the preview.",
    ACCOUNT_FEDERATED_SINCE_PREVIEW: "An account in this file gained an identity at this issuer since the preview.",
}


class FederatedImportRefusal(Exception):
    """Carries a code, never a sentence.

    Rendering an exception is how chained causes and library internals end up
    in an HTTP response; keeping the wording in a table above means the
    response text is chosen, not inherited.
    """

    def __init__(self, code: str, *, line: int | None = None):
        self.code = code
        self.line = line
        super().__init__(code)


class FederatedImportGrantError(FederatedImportRefusal):
    """The confirmation does not correspond to a preview this admin was shown."""


class FederatedImportError(FederatedImportRefusal):
    """The file cannot be read as an import at all."""


class FederatedImportConflict(FederatedImportRefusal):
    """The database changed between planning and applying."""


def message_for(code: object) -> str:
    """The operator-facing wording for a refusal code."""
    return REFUSAL_MESSAGES.get(code, "The file could not be imported.")


@dataclass(frozen=True, slots=True)
class PlannedBinding:
    line: int
    user_id: str
    user_email: str
    email: str
    subject: str
    subject_format: str
    binding_key: str
    existing: bool


@dataclass(frozen=True, slots=True)
class ImportPlan:
    provider: str
    issuer: str
    source_name: str
    input_sha256: str
    row_count: int
    bindings: tuple[PlannedBinding, ...] = ()
    errors: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def existing_count(self) -> int:
        return sum(1 for binding in self.bindings if binding.existing)

    @property
    def new_count(self) -> int:
        return len(self.bindings) - self.existing_count

    def as_report(self, *, dry_run: bool) -> dict:
        return {
            "provider": self.provider,
            "issuer": self.issuer,
            "source": self.source_name,
            "input_sha256": self.input_sha256,
            "dry_run": dry_run,
            "row_count": self.row_count,
            # On a dry run this is what *would* be created, which is the number
            # an operator is deciding on.
            "imported_count": self.new_count,
            "existing_count": self.existing_count,
            "errors": list(self.errors),
        }

    def preview_rows(self) -> list[dict]:
        """What an operator confirms against, one line per row."""
        return [
            {
                "line": binding.line,
                "email": binding.user_email,
                "subject": binding.subject,
                "action": "already-linked" if binding.existing else "link",
            }
            for binding in self.bindings
        ]


def _decode(source_bytes: bytes) -> str:
    try:
        return source_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise FederatedImportError(FILE_NOT_UTF8) from exc


def plan_federated_import(*, provider: str, issuer: str, source_bytes: bytes, source_name: str) -> ImportPlan:
    """Validate a file against the database without writing anything."""
    provider = provider.strip()
    issuer = issuer.strip()
    if not issuer:
        raise FederatedImportError(ISSUER_REQUIRED)
    if provider not in dict(FederatedIdentity.Provider.choices):
        raise FederatedImportError(UNKNOWN_PROVIDER)

    reader = csv.DictReader(_decode(source_bytes).splitlines())
    columns = set(reader.fieldnames or ())
    if not REQUIRED_COLUMNS.issubset(columns):
        raise FederatedImportError(MISSING_SUBJECT_COLUMNS)
    if not IDENTIFIER_COLUMNS & columns:
        raise FederatedImportError(MISSING_IDENTIFIER_COLUMN)

    rows = list(reader)
    errors: list[dict] = []
    bindings: list[PlannedBinding] = []
    seen_bindings: dict[str, int] = {}
    # Two rows pointing a provider at one account are as wrong as one row
    # doing it to an account already linked, and the database cannot tell us:
    # nothing constrains (user, provider, issuer).
    claimed_accounts: dict[str, int] = {}

    for line_number, row in enumerate(rows, start=2):
        subject = (row.get("subject") or "").strip()
        subject_format = (row.get("subject_format") or "").strip()
        email = (row.get("email") or "").strip().lower()
        user_id = (row.get("user_id") or "").strip()

        if not subject or (provider == FederatedIdentity.Provider.SAML and not subject_format):
            errors.append({"line": line_number, "code": INVALID_SUBJECT})
            continue

        binding_key = federated_binding_key(provider, issuer, subject_format, subject)
        if binding_key in seen_bindings:
            errors.append({"line": line_number, "code": DUPLICATE_SUBJECT, "first_line": seen_bindings[binding_key]})
            continue
        seen_bindings[binding_key] = line_number

        if not user_id and not email:
            errors.append({"line": line_number, "code": USER_IDENTIFIER_REQUIRED})
            continue

        users = User.objects.all()
        if user_id:
            users = users.filter(pk=user_id)
        if email:
            users = users.filter(email__iexact=email)
        user = users.first()
        if user is None:
            errors.append({"line": line_number, "code": USER_NOT_FOUND})
            continue

        existing = FederatedIdentity.objects.filter(binding_key=binding_key).first()
        if existing is not None and existing.user_id != user.id:
            errors.append({"line": line_number, "code": BINDING_OWNED_BY_ANOTHER_USER})
            continue

        conflict = _account_already_federated(
            user_id=user.id, provider=provider, issuer=issuer, binding_key=binding_key
        )
        if conflict is not None or str(user.id) in claimed_accounts:
            error = {"line": line_number, "code": ACCOUNT_ALREADY_FEDERATED}
            if str(user.id) in claimed_accounts:
                error["first_line"] = claimed_accounts[str(user.id)]
            errors.append(error)
            continue
        claimed_accounts[str(user.id)] = line_number

        bindings.append(
            PlannedBinding(
                line=line_number,
                user_id=str(user.id),
                user_email=user.email,
                email=email or user.email,
                subject=subject,
                subject_format=subject_format,
                binding_key=binding_key,
                existing=existing is not None,
            )
        )

    return ImportPlan(
        provider=provider,
        issuer=issuer,
        source_name=source_name,
        input_sha256=hashlib.sha256(source_bytes).hexdigest(),
        row_count=len(rows),
        bindings=tuple(bindings),
        errors=tuple(errors),
    )


def _account_already_federated(*, user_id, provider: str, issuer: str, binding_key: str):
    """A second identity at one issuer is a second, independent way in.

    Sign-in resolves an identity by binding_key and logs in whoever it names,
    so adding one to an account that already has one does not replace the way
    that account signs in — it adds another, and the existing one keeps
    working. Re-importing the same file must still be a no-op, so an identity
    with this exact binding_key is not a conflict with itself.
    """
    return (
        FederatedIdentity.objects.filter(user_id=user_id, provider=provider, issuer=issuer)
        .exclude(binding_key=binding_key)
        .first()
    )


def apply_federated_import(plan: ImportPlan, *, actor=None) -> dict:
    """Create the planned identities and record an immutable audit row."""
    if not plan.is_valid:
        raise FederatedImportError(PLAN_HAS_REFUSALS)

    report = plan.as_report(dry_run=False)
    imported = 0
    existing = 0

    with transaction.atomic():
        for binding in plan.bindings:
            identity = FederatedIdentity.objects.select_for_update().filter(binding_key=binding.binding_key).first()
            if identity is not None:
                if str(identity.user_id) != binding.user_id:
                    raise FederatedImportConflict(BINDING_TAKEN_SINCE_PREVIEW, line=binding.line)
                existing += 1
                continue

            # Re-checked under the row lock: the plan was built outside this
            # transaction, so an identity may have appeared since.
            if _account_already_federated(
                user_id=binding.user_id,
                provider=plan.provider,
                issuer=plan.issuer,
                binding_key=binding.binding_key,
            ):
                raise FederatedImportConflict(ACCOUNT_FEDERATED_SINCE_PREVIEW, line=binding.line)

            FederatedIdentity.objects.create(
                user_id=binding.user_id,
                provider=plan.provider,
                issuer=plan.issuer,
                subject_format=binding.subject_format,
                subject=binding.subject,
                email_at_link=binding.email,
                last_email=binding.email,
                metadata={"source": "admin-csv-import", "source_line": binding.line},
            )
            imported += 1

        report["imported_count"] = imported
        report["existing_count"] = existing
        if actor is not None:
            report["actor_id"] = str(actor.id)

        FederatedIdentityImportAudit.objects.create(
            provider=plan.provider,
            issuer=plan.issuer,
            input_sha256=plan.input_sha256,
            source_name=plan.source_name,
            row_count=plan.row_count,
            imported_count=imported,
            existing_count=existing,
            report=report,
        )

    return report


def issue_import_grant(*, actor_id, provider: str, issuer: str, input_sha256: str) -> str:
    """Bind a confirmation to one admin, one file, and one preview.

    The file is not held server-side between the two steps; it is uploaded
    again to confirm. The digest in the grant is what makes that safe — a
    second upload that differs from the previewed one cannot be confirmed
    with the grant issued for the first.
    """
    return signing.dumps(
        {
            "v": 1,
            "nonce": str(uuid4()),
            "actor_id": str(actor_id),
            "provider": provider,
            "issuer": issuer,
            "input_sha256": input_sha256,
        },
        salt=GRANT_SALT,
        compress=True,
    )


def validate_import_grant(token: object, *, actor_id, provider: str, issuer: str, input_sha256: str) -> None:
    if not isinstance(token, str) or not token:
        raise FederatedImportGrantError(GRANT_MISSING)
    try:
        payload = signing.loads(token, salt=GRANT_SALT, max_age=GRANT_TTL_SECONDS)
    except signing.SignatureExpired as error:
        raise FederatedImportGrantError(GRANT_EXPIRED) from error
    except signing.BadSignature as error:
        raise FederatedImportGrantError(GRANT_INVALID) from error

    if not isinstance(payload, dict) or set(payload) != {
        "v",
        "nonce",
        "actor_id",
        "provider",
        "issuer",
        "input_sha256",
    }:
        raise FederatedImportGrantError(GRANT_INVALID)

    expected = {
        "v": 1,
        "actor_id": str(actor_id),
        "provider": provider,
        "issuer": issuer,
        "input_sha256": input_sha256,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        # Covers the case that matters: a different file, or another admin's
        # preview, presented against this confirmation.
        raise FederatedImportGrantError(GRANT_MISMATCH)
