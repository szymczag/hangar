# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Read and set the instance-wide maintenance notice.

The notice needs its own endpoint rather than a field on `/api/instances/`,
which is cached for two hours server-side and fetched once per tab with
`revalidateOnFocus` off. An announcement that only reaches people who reload is
not an announcement.

The read side is anonymous, because the sign-in page has to be able to show a
notice to someone who cannot sign in — which is exactly the outage worth
announcing. That makes it a disclosure surface, so an anonymous caller is served
the notice only when the operator has explicitly published it.

Deliberately no `@cache_response`. It caches the serialized body, and this body
depends on whether the caller is authenticated; a cached anonymous miss would be
served to a signed-in reader, or worse, the reverse. The row is cached instead,
and the gate is applied per request.

The two sides are mounted on different prefixes, and that is load-bearing. The
session middleware selects the instance-admin cookie for any path containing
"instances", so a signed-in person reading the notice from under /api/instances/
would arrive with no application session and be judged anonymous — quietly
reducing every ordinary reader to the sign-in gate below. The public read is
therefore mounted at /api/maintenance/, and only the console endpoint, which
wants the admin cookie, sits under /api/instances/.

The write side is deliberately not gated on `SKIP_ENV_VAR`. The 409 the
configuration endpoint returns exists because those values are never read back
when the environment is authoritative — a premise that simply does not apply to
a row this view reads from its own table. Refusing the write would leave
config-as-code deployments unable to announce anything at all.
"""

# Django imports
from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

# Third party imports
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

# Module imports
from plane.app.views.base import BaseAPIView
from plane.authentication.session import BaseSessionAuthentication
from plane.ext.models import InstanceMaintenanceNotice
from plane.ext.utils.plain_text import PlainTextError, validate_single_line_text
from plane.license.api.permissions import InstanceAdminPermission

CACHE_KEY = "instance:maintenance-notice"
# Short enough that raising a notice reaches people promptly, long enough that
# every tab in the building polling once a minute does not become a query each.
CACHE_TIMEOUT = 10

MESSAGE_MAX_LENGTH = 500


def _notice():
    """The single notice row, or None. Cached briefly; never per-user."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached or None
    notice = InstanceMaintenanceNotice.objects.order_by("created_at").first()
    # `False` distinguishes "looked, found nothing" from "not looked up yet",
    # so an instance that has never set a notice does not query on every poll.
    cache.set(CACHE_KEY, notice or False, CACHE_TIMEOUT)
    return notice


def _forget():
    cache.delete(CACHE_KEY)


def _public_payload(notice, is_authenticated):
    """What a caller may see. `None` means: show nothing."""
    if notice is None or not notice.is_active(timezone.now()):
        return None
    if not is_authenticated and not notice.show_on_sign_in:
        return None
    return {
        "severity": notice.severity,
        "message": notice.message.strip(),
        "starts_at": notice.starts_at,
        "ends_at": notice.ends_at,
        "fingerprint": notice.fingerprint,
    }


def _admin_payload(notice):
    if notice is None:
        return {
            "is_enabled": False,
            "message": "",
            "severity": InstanceMaintenanceNotice.Severity.INFO,
            "starts_at": None,
            "ends_at": None,
            "show_on_sign_in": False,
            "is_active": False,
            "fingerprint": None,
        }
    return {
        "is_enabled": notice.is_enabled,
        "message": notice.message,
        "severity": notice.severity,
        "starts_at": notice.starts_at,
        "ends_at": notice.ends_at,
        "show_on_sign_in": notice.show_on_sign_in,
        "is_active": notice.is_active(timezone.now()),
        "fingerprint": notice.fingerprint,
    }


def _no_store(response):
    # The gating decision above must never be held by a shared cache.
    response["Cache-Control"] = "no-store"
    return response


class InstanceMaintenanceNoticeEndpoint(BaseAPIView):
    """The notice everyone sees, and the form an administrator sets it from."""

    permission_classes = [AllowAny]

    def get(self, request):
        notice = _notice()
        return _no_store(
            Response(
                {"notice": _public_payload(notice, request.user.is_authenticated)},
                status=status.HTTP_200_OK,
            )
        )


class InstanceMaintenanceNoticeAdminEndpoint(BaseAPIView):
    """The console's view of the notice, including one that is not yet active."""

    authentication_classes = [BaseSessionAuthentication]
    permission_classes = [InstanceAdminPermission]

    def get(self, request):
        notice = InstanceMaintenanceNotice.objects.order_by("created_at").first()
        return _no_store(Response(_admin_payload(notice), status=status.HTTP_200_OK))

    @method_decorator(csrf_protect)
    def patch(self, request):
        notice = InstanceMaintenanceNotice.objects.order_by("created_at").first()
        if notice is None:
            notice = InstanceMaintenanceNotice()

        data = request.data

        if "message" in data:
            try:
                notice.message = validate_single_line_text(data.get("message"), max_length=MESSAGE_MAX_LENGTH)
            except PlainTextError as error:
                return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        if "severity" in data:
            severity = (data.get("severity") or "").strip()
            if severity not in InstanceMaintenanceNotice.Severity.values:
                return Response(
                    {"error": "Severity must be one of: " + ", ".join(InstanceMaintenanceNotice.Severity.values) + "."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            notice.severity = severity

        for field in ("starts_at", "ends_at"):
            if field not in data:
                continue
            raw = data.get(field)
            if raw in (None, ""):
                setattr(notice, field, None)
                continue
            parsed = parse_datetime(raw) if isinstance(raw, str) else None
            if parsed is None:
                return Response(
                    {"error": f"{field} must be an ISO 8601 date and time."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if timezone.is_naive(parsed):
                return Response(
                    {"error": f"{field} must include a timezone offset."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            setattr(notice, field, parsed)

        for field in ("is_enabled", "show_on_sign_in"):
            if field in data:
                setattr(notice, field, bool(data.get(field)))

        if notice.starts_at and notice.ends_at and notice.starts_at >= notice.ends_at:
            return Response(
                {"error": "The notice must start before it ends."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if notice.is_enabled and not notice.message.strip():
            return Response(
                {"error": "A notice needs a message before it can be shown."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Catching this here rather than letting someone publish a notice that
        # can never appear, which looks identical to the feature being broken.
        if notice.is_enabled and notice.ends_at and notice.ends_at <= timezone.now():
            return Response(
                {"error": "That window has already ended."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        notice.updated_by_admin = request.user if request.user.is_authenticated else None
        notice.save()
        _forget()

        return _no_store(Response(_admin_payload(notice), status=status.HTTP_200_OK))
