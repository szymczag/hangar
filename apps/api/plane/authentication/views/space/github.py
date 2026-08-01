# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django import
from django.http import HttpResponseRedirect
from django.views import View
from django.utils.http import url_has_allowed_host_and_scheme

# Module imports
from plane.authentication.provider.oauth.github import GitHubOAuthProvider
from plane.authentication.utils.login import user_login
from plane.authentication.utils.oauth_transaction import (
    consume_oauth_transaction,
    start_oauth_transaction,
)
from plane.license.models import Instance
from plane.authentication.utils.host import base_host
from plane.authentication.adapter.error import (
    AUTHENTICATION_ERROR_CODES,
    AuthenticationException,
)
from plane.utils.path_validator import get_safe_redirect_url, validate_next_path, get_allowed_hosts

GITHUB_TRANSACTION_SPACE = "github_oauth_transaction_space"


class GitHubOauthInitiateSpaceEndpoint(View):
    def get(self, request):
        # Get host and next path
        host = base_host(request=request, is_space=True)
        next_path = request.GET.get("next_path")
        next_path = str(validate_next_path(next_path)) if next_path else None
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
            state = start_oauth_transaction(
                request,
                GITHUB_TRANSACTION_SPACE,
                host=host,
                next_path=next_path,
            )
            provider = GitHubOAuthProvider(request=request, state=state, is_space=True)
            auth_url = provider.get_auth_url()
            return HttpResponseRedirect(auth_url)
        except AuthenticationException as e:
            params = e.get_error_dict()
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_space=True), next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)


class GitHubCallbackSpaceEndpoint(View):
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        transaction, valid_transaction = consume_oauth_transaction(request, GITHUB_TRANSACTION_SPACE, state)
        host = transaction.get("host") or base_host(request=request, is_space=True)
        next_path = transaction.get("next_path")

        if not valid_transaction:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GITHUB_OAUTH_PROVIDER_ERROR"],
                error_message="GITHUB_OAUTH_PROVIDER_ERROR",
            )
            params = exc.get_error_dict()
            url = get_safe_redirect_url(
                base_url=host, next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)

        if not code:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GITHUB_OAUTH_PROVIDER_ERROR"],
                error_message="GITHUB_OAUTH_PROVIDER_ERROR",
            )
            params = exc.get_error_dict()
            url = get_safe_redirect_url(
                base_url=host, next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)

        try:
            provider = GitHubOAuthProvider(request=request, code=code, is_space=True)
            user = provider.authenticate()
            # Login the user and record his device info
            user_login(request=request, user=user, is_space=True)
            # Process workspace and project invitations
            # redirect to referer path
            next_path = validate_next_path(next_path=next_path)

            url = f"{host.rstrip('/')}{next_path}"
            if url_has_allowed_host_and_scheme(url, allowed_hosts=get_allowed_hosts()):
                return HttpResponseRedirect(url)
            else:
                return HttpResponseRedirect(host)
        except AuthenticationException as e:
            params = e.get_error_dict()
            url = get_safe_redirect_url(
                base_url=host, next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)
