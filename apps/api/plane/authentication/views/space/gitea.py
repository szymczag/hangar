# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from urllib.parse import urlencode

# Django import
from django.http import HttpResponseRedirect
from django.views import View

# Module imports
from plane.authentication.provider.oauth.gitea import GiteaOAuthProvider
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
from plane.utils.path_validator import validate_next_path

GITEA_TRANSACTION_SPACE = "gitea_oauth_transaction_space"


class GiteaOauthInitiateSpaceEndpoint(View):
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
            if next_path:
                params["next_path"] = str(validate_next_path(next_path))
            url = f"{base_host(request=request, is_space=True)}?{urlencode(params)}"
            return HttpResponseRedirect(url)

        try:
            state = start_oauth_transaction(
                request,
                GITEA_TRANSACTION_SPACE,
                host=host,
                next_path=next_path,
            )
            provider = GiteaOAuthProvider(request=request, state=state, is_space=True)
            auth_url = provider.get_auth_url()
            return HttpResponseRedirect(auth_url)
        except AuthenticationException as e:
            params = e.get_error_dict()
            if next_path:
                params["next_path"] = str(next_path)
            url = f"{base_host(request=request, is_space=True)}?{urlencode(params)}"
            return HttpResponseRedirect(url)


class GiteaCallbackSpaceEndpoint(View):
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        transaction, valid_transaction = consume_oauth_transaction(request, GITEA_TRANSACTION_SPACE, state)
        host = transaction.get("host") or base_host(request=request, is_space=True)
        next_path = transaction.get("next_path")

        if not valid_transaction:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GITEA_OAUTH_PROVIDER_ERROR"],
                error_message="GITEA_OAUTH_PROVIDER_ERROR",
            )
            params = exc.get_error_dict()
            if next_path:
                params["next_path"] = str(validate_next_path(next_path))
            url = f"{host}?{urlencode(params)}"
            return HttpResponseRedirect(url)

        if not code:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["GITEA_OAUTH_PROVIDER_ERROR"],
                error_message="GITEA_OAUTH_PROVIDER_ERROR",
            )
            params = exc.get_error_dict()
            if next_path:
                params["next_path"] = str(validate_next_path(next_path))
            url = f"{host}?{urlencode(params)}"
            return HttpResponseRedirect(url)

        try:
            provider = GiteaOAuthProvider(request=request, code=code, is_space=True)
            user = provider.authenticate()
            # Login the user and record his device info
            user_login(request=request, user=user, is_space=True)
            # Process workspace and project invitations
            # redirect to referer path
            url = (
                f"{host}{str(validate_next_path(next_path)) if next_path else ''}"
            )
            return HttpResponseRedirect(url)
        except AuthenticationException as e:
            params = e.get_error_dict()
            if next_path:
                params["next_path"] = str(validate_next_path(next_path))
            url = f"{host}?{urlencode(params)}"
            return HttpResponseRedirect(url)
