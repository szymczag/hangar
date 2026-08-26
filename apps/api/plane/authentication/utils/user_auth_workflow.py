# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Module imports
from plane.db.models import Profile, WorkspaceMember
from plane.utils.exception_logger import log_exception

from .sso_auto_join import auto_join_projects, auto_join_workspaces
from .workspace_project_join import process_workspace_project_invitations


def _settle_onboarding(user):
    """Record that someone who already belongs somewhere has nowhere to onboard.

    Onboarding routes on the profile's own flags, not on membership. Auto-join
    adds a WorkspaceMember directly and creates no invitation, so a person it
    admitted arrived at the "create a workspace" step with no invitations to
    accept — and, on an instance that restricts workspace creation, no way out
    of that screen at all.

    Fixing it here rather than in the onboarding screens is deliberate: the
    server is what knows a membership was granted, and every client asking
    "is this person onboarded" gets the same answer.
    """
    memberships = (
        WorkspaceMember.objects.filter(member=user, is_active=True).select_related("workspace").order_by("created_at")
    )
    membership = memberships.first()
    if membership is None:
        return

    profile = Profile.objects.filter(user=user).first()
    if profile is None:
        return

    steps = dict(profile.onboarding_step or {})
    # The profile step is left alone: it collects a display name, which nobody
    # else can supply. Only the workspace steps are settled, because belonging
    # to a workspace is what they were asking about.
    already_settled = all(steps.get(key) for key in ("workspace_create", "workspace_join"))
    if already_settled and profile.last_workspace_id:
        return

    steps["workspace_create"] = True
    steps["workspace_join"] = True
    profile.onboarding_step = steps
    if not profile.last_workspace_id:
        profile.last_workspace_id = membership.workspace_id
    profile.save(update_fields=["onboarding_step", "last_workspace_id", "updated_at"])


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
    try:
        _settle_onboarding(user=user)
    except Exception as exc:  # noqa: BLE001 - never block a valid sign-in
        log_exception(exc)
