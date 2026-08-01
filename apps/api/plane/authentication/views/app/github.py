# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django import
from django.http import HttpResponseRedirect
from django.views import View

# Module imports
from plane.authentication.provider.oauth.github import GitHubOAuthProvider
from plane.authentication.utils.login import user_login
from plane.authentication.utils.redirection_path import get_redirection_path
from plane.authentication.utils.user_auth_workflow import post_user_auth_workflow
from plane.authentication.utils.oauth_transaction import (
    consume_oauth_transaction,
    start_oauth_transaction,
)
from plane.license.models import Instance
from plane.authentication.utils.host import base_host
from plane.authentication.adapter.error import (
    AuthenticationException,
    AUTHENTICATION_ERROR_CODES,
)
from plane.utils.path_validator import get_safe_redirect_url

GITHUB_TRANSACTION_APP = "github_oauth_transaction_app"


class GitHubOauthInitiateEndpoint(View):
    def get(self, request):
        # Get host and next path
        host = base_host(request=request, is_app=True)
        next_path = request.GET.get("next_path")
        next_path = str(next_path) if next_path else None

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
            state = start_oauth_transaction(
                request,
                GITHUB_TRANSACTION_APP,
                host=host,
                next_path=next_path,
            )
            provider = GitHubOAuthProvider(request=request, state=state)
            auth_url = provider.get_auth_url()
            return HttpResponseRedirect(auth_url)
        except AuthenticationException as e:
            params = e.get_error_dict()
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_app=True), next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)


class GitHubCallbackEndpoint(View):
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        transaction, valid_transaction = consume_oauth_transaction(request, GITHUB_TRANSACTION_APP, state)
        next_path = transaction.get("next_path")
        host = transaction.get("host") or base_host(request=request, is_app=True)

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
            provider = GitHubOAuthProvider(request=request, code=code, callback=post_user_auth_workflow)
            user = provider.authenticate()
            # Login the user and record his device info
            user_login(request=request, user=user, is_app=True)
            if next_path:
                path = next_path
            else:
                path = get_redirection_path(user=user)

            # Get the safe redirect URL
            url = get_safe_redirect_url(base_url=host, next_path=path, params={})
            return HttpResponseRedirect(url)
        except AuthenticationException as e:
            params = e.get_error_dict()
            url = get_safe_redirect_url(
                base_url=host, next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)
