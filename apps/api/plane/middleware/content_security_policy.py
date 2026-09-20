# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# The API answers with JSON, redirects and file downloads, never with a page
# meant to run code. A policy that allows nothing costs nothing here and keeps
# any response that a browser does end up rendering (an error page, a
# mislabelled download) from loading or running anything.
API_CONTENT_SECURITY_POLICY = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

# drf-spectacular's optional Swagger and Redoc pages are HTML with inline code
# and a CDN; they keep their own behaviour when enabled.
EXEMPT_PREFIXES = ("/api/schema/",)


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith(EXEMPT_PREFIXES):
            response.headers.setdefault("Content-Security-Policy", API_CONTENT_SECURITY_POLICY)
        return response
