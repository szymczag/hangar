# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import logging
import time

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


def health_check(request):
    return JsonResponse({"status": "OK"})


def robots_txt(request):
    return HttpResponse("User-agent: *\nDisallow: /", content_type="text/plain")


# Content-Security-Policy violation reports, sent by browsers while the
# frontends run the policy in report-only mode (HANGAR_CSP_REPORT_ONLY with
# HANGAR_CSP_REPORT_URI=/api/csp-report/). Anyone can post here, so the body is
# size-capped, only the fields that identify the violation are logged, and a
# client gets a bounded number of log lines per minute.
CSP_REPORT_MAX_BYTES = 16 * 1024
CSP_REPORT_PER_MINUTE = 30
CSP_REPORT_FIELDS = (
    "document-uri",
    "effective-directive",
    "violated-directive",
    "blocked-uri",
    "disposition",
    "source-file",
    "line-number",
    "column-number",
    # For Trusted Types the sample names the sink ("Element innerHTML|<p>…"),
    # which is what docs/trusted-types-plan.md needs from these reports.
    "script-sample",
)

csp_logger = logging.getLogger("plane.security.csp")


@csrf_exempt
@require_POST
def csp_report(request):
    if int(request.META.get("CONTENT_LENGTH") or 0) > CSP_REPORT_MAX_BYTES:
        return HttpResponse(status=413)

    client = request.META.get("REMOTE_ADDR", "unknown")
    bucket = f"csp-report:{client}:{int(time.time() // 60)}"
    # add() counts the first report of the minute; incr() every later one.
    if not cache.add(bucket, 1, timeout=60) and cache.incr(bucket) > CSP_REPORT_PER_MINUTE:
        return HttpResponse(status=204)

    try:
        report = json.loads(request.body[:CSP_REPORT_MAX_BYTES] or b"{}").get("csp-report", {})
    except (ValueError, AttributeError):
        return HttpResponse(status=400)
    if not isinstance(report, dict):
        return HttpResponse(status=400)

    fields = {field: str(report.get(field, ""))[:512] for field in CSP_REPORT_FIELDS}
    csp_logger.warning("Content-Security-Policy violation", extra={"csp_report": fields})
    return HttpResponse(status=204)
