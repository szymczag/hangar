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


# Module imports
from plane.authentication.provider.oauth.google import GoogleOAuthProvider
from plane.authentication.utils.login import user_login
from plane.authentication.utils.redirection_path import get_redirection_path
from plane.authentication.utils.user_auth_workflow import post_user_auth_workflow
from plane.license.models import Instance
from plane.authentication.utils.host import base_host
from plane.authentication.adapter.error import (
    AuthenticationException,
    AUTHENTICATION_ERROR_CODES,
)
from plane.utils.path_validator import get_safe_redirect_url
from plane.utils.path_validator import validate_next_path

GOOGLE_TRANSACTION_APP = "google_oauth_transaction_app"
GOOGLE_TRANSACTION_TTL = 60 * 10


def _pkce_pair():
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


class GoogleOauthInitiateEndpoint(View):
    def get(self, request):
        host = base_host(request=request, is_app=True)
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
                base_url=base_host(request=request, is_app=True), next_path=next_path, params=params
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
            )
            request.session[GOOGLE_TRANSACTION_APP] = {
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
                base_url=base_host(request=request, is_app=True), next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)


class GoogleCallbackEndpoint(View):
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        transaction = request.session.pop(GOOGLE_TRANSACTION_APP, None)
        next_path = (transaction or {}).get("next_path")
        host = (transaction or {}).get("host") or base_host(request=request, is_app=True)
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
            )
            user = provider.authenticate()
            # Login the user and record his device info
            user_login(request=request, user=user, is_app=True)
            # Get the redirection path
            if next_path:
                path = next_path
            else:
                path = get_redirection_path(user=user)
            url = get_safe_redirect_url(base_url=host, next_path=path, params={})
            return HttpResponseRedirect(url)
        except AuthenticationException as e:
            params = e.get_error_dict()
            url = get_safe_redirect_url(base_url=host, next_path=next_path, params=params)
            return HttpResponseRedirect(url)
