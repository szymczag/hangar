# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Place federated users into a workspace on sign-in.

Without this an operator who federates a domain still has to invite every
person by hand: signing in produces an account with no membership, which by
design can see nothing. That is the safe default, but for a company whose
whole directory belongs in one workspace it is pure friction.

Auto-join is deliberately gated on the domain being pinned by
``SSO_ENFORCED_DOMAINS``. Membership is granted on the strength of an email
domain, so that domain must first be one only a designated identity provider
may assert; otherwise anyone able to obtain an address at the domain — or to
sign in through some other enabled method — would be handed a seat.
"""

# Python imports
import os

# Django imports
from django.db import transaction

# Module imports
from plane.authentication.utils.sso_domain_policy import (
    _normalize_domain,
    allowed_providers_for_email,
)
from plane.db.models import Project, ProjectMember, Workspace, WorkspaceMember
from plane.license.utils.instance_value import get_configuration_value
from plane.utils.exception_logger import log_exception

# Role names an operator may write in the configuration, mapped to the stored
# numeric role. Kept explicit rather than importing ROLE so that a change to
# the enum cannot silently redefine what an existing configuration grants.
ROLE_NAMES = {"admin": 20, "member": 15, "guest": 5}
DEFAULT_ROLE = ROLE_NAMES["guest"]


def parse_auto_join(raw):
    """Parse ``SSO_AUTO_JOIN_WORKSPACES`` into {domain: [(slug, role)]}.

    Entries look like ``corp.com=engineering:member``. The role is optional and
    defaults to guest, the least that can be granted: an operator who does not
    state a role should not accidentally hand out write access.

    Unparseable entries are skipped rather than raising, so one typo cannot
    stop the rest of a directory from signing in.
    """
    policy = {}
    for entry in str(raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        domain, separator, target = entry.partition("=")
        domain = _normalize_domain(domain)
        if not domain or not separator:
            continue

        slug, _, role_name = target.partition(":")
        slug = slug.strip().lower()
        if not slug:
            continue

        role_name = role_name.strip().lower()
        if role_name and role_name not in ROLE_NAMES:
            # An unrecognised role must not silently become a privileged one.
            continue

        policy.setdefault(domain, []).append((slug, ROLE_NAMES.get(role_name, DEFAULT_ROLE)))
    return policy


def parse_auto_join_projects(raw):
    """Parse ``SSO_AUTO_JOIN_PROJECTS`` into {domain: [(slug, identifier, role)]}.

    Entries look like ``corp.com=engineering/PLAT:member``, naming the workspace
    slug and the project identifier. The identifier rather than a uuid, because
    an operator typing this into the admin panel has the identifier in front of
    them and a uuid is unreadable.

    Same failure policy as the workspace form: role defaults to guest, an
    unrecognised role drops the entry rather than becoming something
    privileged, and a malformed entry is skipped without taking the rest with
    it.
    """
    policy = {}
    for entry in str(raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        domain, separator, target = entry.partition("=")
        domain = _normalize_domain(domain)
        if not domain or not separator:
            continue

        location, _, role_name = target.partition(":")
        slug, slash, identifier = location.partition("/")
        slug = slug.strip().lower()
        identifier = identifier.strip()
        if not slug or not slash or not identifier:
            continue

        role_name = role_name.strip().lower()
        if role_name and role_name not in ROLE_NAMES:
            continue

        policy.setdefault(domain, []).append((slug, identifier, ROLE_NAMES.get(role_name, DEFAULT_ROLE)))
    return policy


def _configured_auto_join_projects():
    (raw,) = get_configuration_value(
        [
            {
                "key": "SSO_AUTO_JOIN_PROJECTS",
                "default": os.environ.get("SSO_AUTO_JOIN_PROJECTS", ""),
            }
        ]
    )
    return parse_auto_join_projects(raw)


def _targets_for(policy, user, provider):
    """Entries that apply to this sign-in, or an empty list.

    The pinning check lives here so workspace and project joining cannot drift
    apart: granting a seat on the strength of an email domain requires that
    domain to belong to a designated provider, or any other enabled sign-in
    method becomes a way in.
    """
    if not policy:
        return []

    _, separator, domain = str(user.email or "").rpartition("@")
    if not separator:
        return []
    targets = policy.get(_normalize_domain(domain))
    if not targets:
        return []

    allowed = allowed_providers_for_email(user.email)
    if not allowed or (provider is not None and provider not in allowed):
        return []
    return targets


def _configured_auto_join():
    (raw,) = get_configuration_value(
        [
            {
                "key": "SSO_AUTO_JOIN_WORKSPACES",
                "default": os.environ.get("SSO_AUTO_JOIN_WORKSPACES", ""),
            }
        ]
    )
    return parse_auto_join(raw)


def auto_join_workspaces(user, provider=None):
    """Add ``user`` to every workspace configured for their email domain.

    Idempotent: an existing membership is never modified, so a role an admin
    lowered by hand is not restored on the next sign-in, and a member who was
    deactivated is not silently reactivated.
    """
    targets = _targets_for(_configured_auto_join(), user, provider)
    joined = []
    for slug, role in targets:
        try:
            with transaction.atomic():
                workspace = Workspace.objects.filter(slug=slug).first()
                if workspace is None:
                    continue
                _, created = WorkspaceMember.objects.get_or_create(
                    workspace=workspace,
                    member=user,
                    defaults={"role": role, "is_active": True},
                )
                if created:
                    joined.append((slug, role))
        except Exception as exc:  # noqa: BLE001 - never block a valid sign-in
            log_exception(exc)
    return joined


def auto_join_projects(user, provider=None):
    """Add ``user`` to every project configured for their email domain.

    Requires an existing workspace membership rather than creating one. A
    ProjectMember without a WorkspaceMember is a state the rest of the model
    does not expect, and silently manufacturing the workspace seat would grant
    more than the operator asked for in this setting.

    Archived projects are skipped: joining someone to a project that has been
    put away is not what the configuration means.
    """
    targets = _targets_for(_configured_auto_join_projects(), user, provider)
    joined = []

    for slug, identifier, role in targets:
        try:
            with transaction.atomic():
                project = Project.objects.filter(
                    workspace__slug=slug,
                    identifier=identifier,
                    archived_at__isnull=True,
                ).first()
                if project is None:
                    continue

                if not WorkspaceMember.objects.filter(
                    workspace_id=project.workspace_id, member=user, is_active=True
                ).exists():
                    continue

                # objects.create through get_or_create, never bulk_create:
                # ProjectMember.save() also creates the ProjectUserProperty row
                # this member needs, and bulk_create would skip it.
                _, created = ProjectMember.objects.get_or_create(
                    workspace_id=project.workspace_id,
                    project=project,
                    member=user,
                    defaults={"role": role, "is_active": True},
                )
                if created:
                    joined.append((slug, identifier, role))
        except Exception as exc:  # noqa: BLE001 - never block a valid sign-in
            log_exception(exc)
    return joined
