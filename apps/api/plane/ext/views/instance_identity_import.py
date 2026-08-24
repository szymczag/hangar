# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Console upload for federated identity imports.

This grants sign-in access to existing accounts, so it is deliberately the
most guarded endpoint in the console:

- it lives under a path containing "instances", because the session middleware
  selects the admin cookie by that substring (plane/authentication/middleware/
  session.py) — mounted elsewhere it would read the *application* session;
- `InstanceAdminPermission` already requires the WebAuthn second factor, so a
  stolen console password alone cannot reach it;
- confirming additionally requires the admin's password re-entered here. The
  key proves the session; the password proves the person at the keyboard right
  now, which is the property that matters for an operation nobody else will
  review.

The file is never held between preview and confirm. It is uploaded twice and
the signed grant carries its digest, so the file that is applied is provably
the file that was shown.
"""

# Django imports
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

# Third party imports
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

# Module imports
from plane.authentication.session import BaseSessionAuthentication
from plane.db.models import FederatedIdentity
from plane.ext.services.federated_import import (
    FederatedImportConflict,
    FederatedImportError,
    FederatedImportGrantError,
    apply_federated_import,
    issue_import_grant,
    plan_federated_import,
    validate_import_grant,
)
from plane.license.api.permissions import InstanceAdminPermission
from plane.utils.exception_logger import log_exception
from plane.app.views.base import BaseAPIView

# Matches the Todoist importer's ceiling. A directory export large enough to
# exceed this belongs in the CLI, which streams from disk.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _error(code: str, message: str, response_status=status.HTTP_400_BAD_REQUEST) -> Response:
    return Response({"error": {"code": code, "message": message}}, status=response_status)


class InstanceIdentityImportEndpoint(BaseAPIView):
    """POST a CSV to preview it; POST again with the grant to apply it."""

    authentication_classes = [BaseSessionAuthentication]
    permission_classes = [InstanceAdminPermission]
    parser_classes = [MultiPartParser, FormParser]

    @method_decorator(csrf_protect)
    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return _error("file_required", "Attach the CSV of identity mappings.")
        if upload.size > MAX_UPLOAD_BYTES:
            return _error("file_too_large", "The CSV file exceeds the 5 MiB import limit.")

        provider = (request.data.get("provider") or "").strip()
        issuer = (request.data.get("issuer") or "").strip()
        source_bytes = upload.read()

        try:
            plan = plan_federated_import(
                provider=provider,
                issuer=issuer,
                source_bytes=source_bytes,
                source_name=upload.name or "upload.csv",
            )
        except FederatedImportError as exc:
            return _error("invalid_file", str(exc))

        if not plan.is_valid:
            # Refusals are the whole point of the preview step, so they are a
            # normal 200 answer describing the file, not a transport error.
            return Response(
                {
                    "valid": False,
                    "report": plan.as_report(dry_run=True),
                    "rows": plan.preview_rows(),
                },
                status=status.HTTP_200_OK,
            )

        confirm = str(request.data.get("confirm") or "").lower() == "true"
        if not confirm:
            return Response(
                {
                    "valid": True,
                    "report": plan.as_report(dry_run=True),
                    "rows": plan.preview_rows(),
                    "grant": issue_import_grant(
                        actor_id=request.user.id,
                        provider=plan.provider,
                        issuer=plan.issuer,
                        input_sha256=plan.input_sha256,
                    ),
                },
                status=status.HTTP_200_OK,
            )

        try:
            validate_import_grant(
                request.data.get("grant"),
                actor_id=request.user.id,
                provider=plan.provider,
                issuer=plan.issuer,
                input_sha256=plan.input_sha256,
            )
        except FederatedImportGrantError as exc:
            return _error("invalid_grant", str(exc), status.HTTP_409_CONFLICT)

        password = request.data.get("password") or ""
        if not password or not request.user.check_password(password):
            return _error(
                "password_required",
                "Re-enter your password to apply an identity import.",
                status.HTTP_403_FORBIDDEN,
            )

        try:
            report = apply_federated_import(plan, actor=request.user)
        except FederatedImportConflict as exc:
            # Something linked an identity between the preview and now; the
            # transaction rolled back, so the operator previews again.
            return _error("import_conflict", str(exc), status.HTTP_409_CONFLICT)
        except FederatedImportError as exc:
            return _error("invalid_file", str(exc))
        except Exception as exc:  # noqa: BLE001 - never leak the internals of this one
            log_exception(exc)
            return _error(
                "import_failed",
                "The import was rolled back.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"valid": True, "report": report}, status=status.HTTP_200_OK)

    def get(self, request):
        """The providers an import may name, so the console need not hardcode them."""
        return Response(
            {"providers": [choice[0] for choice in FederatedIdentity.Provider.choices]},
            status=status.HTTP_200_OK,
        )
