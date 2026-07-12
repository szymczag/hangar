# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import base64
import hashlib
import secrets
import uuid
from urllib.parse import urlencode, urljoin

# Django imports
from django.http import HttpResponseRedirect
from django.views import View

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
from plane.ext.auth.provider.oidc import OIDCOAuthProvider

SESSION_STATE = "oidc_state"
SESSION_NONCE = "oidc_nonce"
SESSION_VERIFIER = "oidc_code_verifier"


def _pkce_pair():
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _error_redirect(host, exc_params, next_path):
    params = dict(exc_params)
    if next_path:
        params["next_path"] = str(validate_next_path(next_path))
    return HttpResponseRedirect(urljoin(host, "?" + urlencode(params)))


class OIDCEndpointMixin:
    is_space = False

    def _host(self, request):
        if self.is_space:
            return base_host(request=request, is_space=True)
        return base_host(request=request, is_app=True)

    def _session_key(self, key):
        # App and Space authorization attempts may coexist in one browser
        # session. Keep their one-shot values separate to prevent one flow
        # from overwriting or being consumed by the other.
        return f"{key}_space" if self.is_space else key


class OIDCAuthInitiateBase(OIDCEndpointMixin, View):
    def get(self, request):
        host = self._host(request)
        request.session["host"] = host
        next_path = request.GET.get("next_path")
        if next_path:
            request.session["next_path"] = str(validate_next_path(next_path))

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
            state = uuid.uuid4().hex
            nonce = uuid.uuid4().hex
            code_verifier, code_challenge = _pkce_pair()
            provider = OIDCOAuthProvider(
                request=request,
                state=state,
                nonce=nonce,
                code_challenge=code_challenge,
                is_space=self.is_space,
            )
            request.session[self._session_key(SESSION_STATE)] = state
            request.session[self._session_key(SESSION_NONCE)] = nonce
            request.session[self._session_key(SESSION_VERIFIER)] = code_verifier
            return HttpResponseRedirect(provider.get_auth_url())
        except AuthenticationException as e:
            return _error_redirect(host, e.get_error_dict(), next_path)


class OIDCCallbackBase(OIDCEndpointMixin, View):
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        host = request.session.get("host") or self._host(request)
        next_path = request.session.get("next_path")

        # One-shot session values: pop them so a replayed callback URL cannot
        # reuse this session's state/nonce/verifier.
        session_state = request.session.pop(self._session_key(SESSION_STATE), "")
        nonce = request.session.pop(self._session_key(SESSION_NONCE), "")
        code_verifier = request.session.pop(self._session_key(SESSION_VERIFIER), "")

        if not state or state != session_state or not code:
            exc = AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_ERROR"],
                error_message="OIDC_PROVIDER_ERROR",
            )
            return _error_redirect(host, exc.get_error_dict(), next_path)

        try:
            provider = OIDCOAuthProvider(
                request=request,
                code=code,
                nonce=nonce,
                code_verifier=code_verifier,
                callback=post_user_auth_workflow,
                is_space=self.is_space,
            )
            user = provider.authenticate()
            if self.is_space:
                user_login(request=request, user=user, is_space=True)
                path = str(validate_next_path(next_path)) if next_path else ""
            else:
                user_login(request=request, user=user, is_app=True)
                path = str(validate_next_path(next_path)) if next_path else get_redirection_path(user=user)
            return HttpResponseRedirect(urljoin(host, path))
        except AuthenticationException as e:
            return _error_redirect(host, e.get_error_dict(), next_path)


class OIDCAuthInitiateEndpoint(OIDCAuthInitiateBase):
    is_space = False


class OIDCCallbackEndpoint(OIDCCallbackBase):
    is_space = False


class OIDCAuthInitiateSpaceEndpoint(OIDCAuthInitiateBase):
    is_space = True


class OIDCCallbackSpaceEndpoint(OIDCCallbackBase):
    is_space = True
