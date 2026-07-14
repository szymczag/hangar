# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import hashlib
import hmac
import secrets
import string
import uuid
from urllib.parse import urlencode, urljoin

# Django imports
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

# Module imports
from plane.authentication.adapter.error import (
    AUTHENTICATION_ERROR_CODES,
    AuthenticationException,
)
from plane.authentication.rate_limit import authentication_throttle_allows
from plane.authentication.utils.host import base_host
from plane.authentication.utils.login import user_login
from plane.authentication.utils.redirection_path import get_redirection_path
from plane.authentication.utils.user_auth_workflow import post_user_auth_workflow
from plane.license.models import Instance
from plane.utils.path_validator import validate_next_path

from plane.ext.auth.error import EXT_AUTHENTICATION_ERROR_CODES
from plane.ext.auth.provider.saml import SAMLProvider

# The IdP posts the assertion back cross-site, so the browser does not attach
# the (SameSite=Lax) session cookie to the ACS request. Flow state therefore
# lives in the cache, keyed by a single-use opaque RelayState token instead of
# in the session. The token only selects which pending AuthnRequest ID to
# enforce InResponseTo against — trust still comes from the IdP signature.
RELAY_STATE_TTL = 60 * 10
SAML_CORRELATION_COOKIE_PATH = "/auth/saml/callback/"


def _relay_key(token):
    return f"ext:saml:relay:{token}"


def _relay_claim_key(token):
    return f"ext:saml:relay-claimed:{token}"


def _correlation_cookie_name(token):
    if len(token) != 32 or any(character not in string.hexdigits for character in token):
        return None
    return f"saml_flow_{token[:16].lower()}"


def _clear_correlation_cookie(response, relay_token):
    cookie_name = _correlation_cookie_name(relay_token)
    if cookie_name:
        response.delete_cookie(
            cookie_name,
            path=SAML_CORRELATION_COOKIE_PATH,
            samesite="None",
        )
    return response


def _error_redirect(host, exc_params, next_path):
    params = dict(exc_params)
    if next_path:
        params["next_path"] = str(validate_next_path(next_path))
    return HttpResponseRedirect(urljoin(host, "?" + urlencode(params)))


class SAMLAuthInitiateEndpoint(View):
    def get(self, request):
        host = base_host(request=request, is_app=True)
        next_path = request.GET.get("next_path")

        if not authentication_throttle_allows(request):
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["RATE_LIMIT_EXCEEDED"],
                error_message="RATE_LIMIT_EXCEEDED",
            )
            return _error_redirect(host, exc.get_error_dict(), next_path)

        # Check instance configuration
        instance = Instance.objects.first()
        if instance is None or not instance.is_setup_done:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["INSTANCE_NOT_CONFIGURED"],
                error_message="INSTANCE_NOT_CONFIGURED",
            )
            return _error_redirect(host, exc.get_error_dict(), next_path)

        try:
            provider = SAMLProvider(request=request)
            auth = provider.get_saml_auth()
            relay_token = uuid.uuid4().hex
            browser_secret = secrets.token_urlsafe(32)
            login_url = auth.login(return_to=relay_token)
            cache.set(
                _relay_key(relay_token),
                {
                    "request_id": auth.get_last_request_id(),
                    "host": host,
                    "next_path": str(validate_next_path(next_path)) if next_path else None,
                    "browser_secret_digest": hashlib.sha256(browser_secret.encode("ascii")).hexdigest(),
                },
                RELAY_STATE_TTL,
            )
            response = HttpResponseRedirect(login_url)
            response.set_cookie(
                _correlation_cookie_name(relay_token),
                browser_secret,
                max_age=RELAY_STATE_TTL,
                secure=True,
                httponly=True,
                samesite="None",
                path=SAML_CORRELATION_COOKIE_PATH,
            )
            return response
        except AuthenticationException as e:
            return _error_redirect(host, e.get_error_dict(), next_path)


@method_decorator(csrf_exempt, name="dispatch")
class SAMLCallbackEndpoint(View):
    """Assertion Consumer Service.

    CSRF-exempt by necessity (the IdP cannot send a Django CSRF token); no
    state is mutated before the SAML signature is validated, and the
    RelayState token is single-use.
    """

    def post(self, request):
        relay_token = request.POST.get("RelayState", "")
        flow = cache.get(_relay_key(relay_token)) if relay_token else None
        cookie_name = _correlation_cookie_name(relay_token)
        browser_secret = request.COOKIES.get(cookie_name, "") if cookie_name else ""
        browser_secret_digest = hashlib.sha256(browser_secret.encode("utf-8")).hexdigest() if browser_secret else ""
        expected_digest = (flow or {}).get("browser_secret_digest", "")

        # Verify browser correlation before claiming the flow. A forwarded
        # RelayState/SAMLResponse must not consume the initiating browser's
        # legitimate transaction.
        if (
            not browser_secret_digest
            or not expected_digest
            or not hmac.compare_digest(browser_secret_digest, expected_digest)
        ):
            flow = None

        # cache.add is atomic across workers. Two concurrent requests may both
        # read the flow, but only one can claim and consume it.
        if flow and cache.add(_relay_claim_key(relay_token), "1", RELAY_STATE_TTL):
            cache.delete(_relay_key(relay_token))
        else:
            flow = None

        host = (flow or {}).get("host") or base_host(request=request, is_app=True)
        next_path = (flow or {}).get("next_path")

        if not flow:
            exc = AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["INVALID_SAML_RESPONSE"],
                error_message="INVALID_SAML_RESPONSE",
            )
            return _clear_correlation_cookie(
                _error_redirect(host, exc.get_error_dict(), next_path),
                relay_token,
            )

        try:
            provider = SAMLProvider(request=request, callback=post_user_auth_workflow)
            user = provider.authenticate(request_id=flow.get("request_id"))
            user_login(request=request, user=user, is_app=True)
            path = str(validate_next_path(next_path)) if next_path else get_redirection_path(user=user)
            return _clear_correlation_cookie(HttpResponseRedirect(urljoin(host, path)), relay_token)
        except AuthenticationException as e:
            return _clear_correlation_cookie(_error_redirect(host, e.get_error_dict(), next_path), relay_token)


class SAMLMetadataEndpoint(View):
    """Public SP metadata for IdP configuration."""

    def get(self, request):
        try:
            # Metadata must remain available while the provider is disabled so
            # administrators can configure the IdP before enabling sign-in.
            provider = SAMLProvider(request=request, require_enabled=False)
            metadata = provider.get_sp_metadata()
            return HttpResponse(metadata, content_type="text/xml")
        except AuthenticationException as e:
            return HttpResponse(
                str(e.get_error_dict().get("error_message")),
                status=404,
                content_type="text/plain",
            )
