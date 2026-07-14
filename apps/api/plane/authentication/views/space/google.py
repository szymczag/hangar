# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import base64
import hashlib
import hmac
import secrets
import time

# Django import
from django.http import HttpResponseRedirect
from django.views import View
from django.utils.http import url_has_allowed_host_and_scheme

# Module imports
from plane.authentication.provider.oauth.google import GoogleOAuthProvider
from plane.authentication.utils.login import user_login
from plane.authentication.utils.user_auth_workflow import post_user_auth_workflow
from plane.license.models import Instance
from plane.authentication.utils.host import base_host
from plane.authentication.adapter.error import (
    AuthenticationException,
    AUTHENTICATION_ERROR_CODES,
)
from plane.utils.path_validator import get_safe_redirect_url, validate_next_path, get_allowed_hosts

GOOGLE_TRANSACTION_SPACE = "google_oauth_transaction_space"
GOOGLE_TRANSACTION_TTL = 60 * 10


def _pkce_pair():
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


class GoogleOauthInitiateSpaceEndpoint(View):
    def get(self, request):
        host = base_host(request=request, is_space=True)
        next_path = request.GET.get("next_path")
        if next_path:
            next_path = str(validate_next_path(next_path))

        # Check instance configuration
        instance = Instance.objects.first()
        if instance is None or not instance.is_setup_done:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["INSTANCE_NOT_CONFIGURED"],
                error_message="INSTANCE_NOT_CONFIGURED",
            )
            params = exc.get_error_dict()
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_space=True), next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)

        try:
            state = secrets.token_urlsafe(32)
            nonce = secrets.token_urlsafe(32)
            code_verifier, code_challenge = _pkce_pair()
            provider = GoogleOAuthProvider(
                request=request,
                state=state,
                nonce=nonce,
                code_challenge=code_challenge,
                is_space=True,
            )
            request.session[GOOGLE_TRANSACTION_SPACE] = {
                "state": state,
                "nonce": nonce,
                "code_verifier": code_verifier,
                "host": host,
                "next_path": next_path,
                "created_at": time.time(),
            }
            auth_url = provider.get_auth_url()
            return HttpResponseRedirect(auth_url)
        except AuthenticationException as e:
            params = e.get_error_dict()
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_space=True), next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)


class GoogleCallbackSpaceEndpoint(View):
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        transaction = request.session.pop(GOOGLE_TRANSACTION_SPACE, None)
        host = (transaction or {}).get("host") or base_host(request=request, is_space=True)
        next_path = (transaction or {}).get("next_path")
        expected_state = (transaction or {}).get("state", "")
        created_at = (transaction or {}).get("created_at", 0)

        if (
            not code
            or not state
            or not expected_state
            or not hmac.compare_digest(state, expected_state)
            or not isinstance(created_at, (int, float))
            or time.time() - created_at > GOOGLE_TRANSACTION_TTL
        ):
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GOOGLE_OAUTH_PROVIDER_ERROR"],
                error_message="GOOGLE_OAUTH_PROVIDER_ERROR",
            )
            params = exc.get_error_dict()
            url = get_safe_redirect_url(base_url=host, next_path=next_path, params=params)
            return HttpResponseRedirect(url)
        try:
            provider = GoogleOAuthProvider(
                request=request,
                code=code,
                nonce=transaction["nonce"],
                code_verifier=transaction["code_verifier"],
                callback=post_user_auth_workflow,
                is_space=True,
            )
            user = provider.authenticate()
            # Login the user and record his device info
            user_login(request=request, user=user, is_space=True)
            # redirect to referer path
            next_path = str(validate_next_path(next_path=next_path)) if next_path else ""

            url = f"{host.rstrip('/')}{next_path}"
            if url_has_allowed_host_and_scheme(url, allowed_hosts=get_allowed_hosts()):
                return HttpResponseRedirect(url)
            else:
                return HttpResponseRedirect(host)
        except AuthenticationException as e:
            params = e.get_error_dict()
            url = get_safe_redirect_url(base_url=host, next_path=next_path, params=params)
            return HttpResponseRedirect(url)
