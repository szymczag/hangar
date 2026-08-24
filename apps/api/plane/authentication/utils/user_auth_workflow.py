# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from .sso_auto_join import auto_join_projects, auto_join_workspaces
from .workspace_project_join import process_workspace_project_invitations


def post_user_auth_workflow(user, is_signup, request):
    process_workspace_project_invitations(user=user)
    # Runs on every sign-in, not only signup, so that adding a domain to the
    # auto-join configuration takes effect for people who already have an
    # account. Reaching this point means the domain policy already accepted
    # the provider that authenticated the user.
    auto_join_workspaces(user=user)
    # After the workspace pass: a project seat requires the workspace seat, so
    # ordering these the other way would skip everyone on their first sign-in.
    auto_join_projects(user=user)
