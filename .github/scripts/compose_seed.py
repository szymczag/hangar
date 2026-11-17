# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Seed a Compose deployment with known data, or fingerprint what is there.

Runs inside the api container, fed on standard input:

    docker compose exec -T -e SEED_PASSWORD=... -e SEED_API_TOKEN=... \\
        api python - --seed < compose_seed.py

``--seed`` creates the data and prints its fingerprint; ``--verify`` only
prints the fingerprint. compose-upgrade.sh compares the two across an
upgrade and a restore. The fingerprint is deterministic: it holds counts,
names, roles and the SHA-256 of the uploaded file read back from object
storage, never identifiers, timestamps or password hashes, and it does not
include the password or the API token, which come from the environment.

The script must run against the release being upgraded from as well as the
candidate, so it uses only models and fields both have.
"""

import hashlib
import io
import json
import os
import sys

MARKER = "HANGAR_FINGERPRINT "
WORKSPACES = (
    ("upgrade-alpha", "Upgrade Alpha"),
    ("upgrade-beta", "Upgrade Beta"),
)
# email -> (first name, role in upgrade-alpha, role in upgrade-beta or None)
USERS = {
    "admin@upgrade.hangar.invalid": ("Ada", 20, 15),
    "member@upgrade.hangar.invalid": ("Mel", 15, 20),
    "guest@upgrade.hangar.invalid": ("Gus", 5, None),
}
ADMIN_EMAIL = "admin@upgrade.hangar.invalid"
PROJECT_IDENTIFIER = "UPG"
ISSUE_NAME = "Upgrade survives with its data"
COMMENT_HTML = "<p>Written before the upgrade.</p>"
WORKLOG_MINUTES = 95
WORKLOG_DESCRIPTION = "Time logged before the upgrade"
ATTACHMENT_NAME = "upgrade-evidence.txt"
# Deterministic content, so the fingerprint is the same on every run.
ATTACHMENT_BYTES = b"".join(f"hangar upgrade evidence line {line:04d}\n".encode() for line in range(256))
API_TOKEN_LABEL = "compose-upgrade"


def setup_django():
    sys.path.insert(0, os.getcwd())
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plane.settings.production")
    import django

    django.setup()


def required_env(name):
    value = os.environ.get(name, "")
    if len(value) < 16:
        raise SystemExit(f"{name} must be set to at least 16 characters")
    return value


def seed(password, api_token):
    from django.db import transaction

    from plane.db.models import (
        APIToken,
        FileAsset,
        Issue,
        IssueComment,
        Project,
        ProjectMember,
        State,
        User,
        Workspace,
        WorkspaceMember,
    )
    from plane.ext.models.worklog import IssueWorkLog
    from plane.license.models import Instance
    from plane.settings.storage import S3Storage

    if Workspace.objects.filter(slug=WORKSPACES[0][0]).exists():
        raise SystemExit("The deployment is already seeded")

    instance = Instance.objects.first()
    if instance is None:
        raise SystemExit("The API has not registered the instance yet")

    with transaction.atomic():
        # Password sign-in is refused until the instance is set up.
        Instance.objects.filter(pk=instance.pk).update(is_setup_done=True)

        users = {}
        for email, (first_name, _alpha_role, _beta_role) in USERS.items():
            user = User.objects.create(
                email=email,
                username=email.split("@")[0],
                first_name=first_name,
                last_name="Upgrade",
                is_active=True,
                is_email_verified=True,
            )
            user.set_password(password)
            user.save()
            users[email] = user

        admin = users[ADMIN_EMAIL]
        workspaces = {}
        for slug, name in WORKSPACES:
            workspace = Workspace.objects.create(name=name, slug=slug, owner=admin)
            workspaces[slug] = workspace

        for email, (_first_name, alpha_role, beta_role) in USERS.items():
            WorkspaceMember.objects.create(workspace=workspaces["upgrade-alpha"], member=users[email], role=alpha_role)
            if beta_role is not None:
                WorkspaceMember.objects.create(
                    workspace=workspaces["upgrade-beta"], member=users[email], role=beta_role
                )

        alpha = workspaces["upgrade-alpha"]
        project = Project.objects.create(
            name="Upgrade Project",
            identifier=PROJECT_IDENTIFIER,
            workspace=alpha,
            network=0,
            project_lead=admin,
        )
        for email, (_first_name, alpha_role, _beta_role) in USERS.items():
            ProjectMember.objects.create(project=project, workspace=alpha, member=users[email], role=alpha_role)

        state = State.objects.create(
            name="Backlog", group="backlog", color="#60646C", default=True, project=project, workspace=alpha
        )
        issue = Issue.objects.create(
            name=ISSUE_NAME,
            description_html="<p>Seeded by compose_seed.py.</p>",
            priority="high",
            state=state,
            project=project,
            workspace=alpha,
        )
        IssueComment.objects.create(
            comment_html=COMMENT_HTML,
            actor=admin,
            issue=issue,
            project=project,
            workspace=alpha,
        )
        IssueWorkLog.objects.create(
            issue=issue,
            logged_by=users["member@upgrade.hangar.invalid"],
            duration=WORKLOG_MINUTES,
            description=WORKLOG_DESCRIPTION,
            project=project,
            workspace=alpha,
        )
        APIToken.objects.create(user=admin, label=API_TOKEN_LABEL, token=api_token, workspace=alpha)

        key = f"{alpha.id}/{hashlib.sha256(ATTACHMENT_BYTES).hexdigest()[:32]}-{ATTACHMENT_NAME}"
        FileAsset.objects.create(
            attributes={"name": ATTACHMENT_NAME, "type": "text/plain", "size": len(ATTACHMENT_BYTES)},
            asset=key,
            entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
            entity_identifier=str(issue.id),
            workspace=alpha,
            project=project,
            issue=issue,
            size=len(ATTACHMENT_BYTES),
            is_uploaded=True,
        )

    if not S3Storage().upload_file(io.BytesIO(ATTACHMENT_BYTES), key, content_type="text/plain"):
        raise SystemExit("Uploading the attachment to object storage failed")


def stored_object_sha256(key):
    from plane.settings.storage import S3Storage

    storage = S3Storage()
    response = storage.s3_client.get_object(Bucket=storage.aws_storage_bucket_name, Key=key)
    body = response["Body"]
    try:
        return hashlib.sha256(body.read()).hexdigest()
    finally:
        body.close()


def fingerprint(password, api_token):
    from plane.db.models import (
        APIToken,
        FileAsset,
        Issue,
        IssueComment,
        Project,
        ProjectMember,
        User,
        Workspace,
        WorkspaceMember,
    )
    from plane.ext.models.worklog import IssueWorkLog
    from plane.license.models import Instance

    slugs = [slug for slug, _name in WORKSPACES]
    users = User.objects.filter(email__in=USERS).order_by("email")
    workspace_members = WorkspaceMember.objects.filter(workspace__slug__in=slugs).order_by(
        "workspace__slug", "member__email"
    )
    project = Project.objects.get(workspace__slug="upgrade-alpha", identifier=PROJECT_IDENTIFIER)
    issues = Issue.issue_objects.filter(project=project).order_by("sequence_id")
    comments = IssueComment.objects.filter(project=project).order_by("comment_stripped")
    worklogs = IssueWorkLog.objects.filter(project=project).order_by("duration")
    assets = FileAsset.objects.filter(project=project, entity_type="ISSUE_ATTACHMENT").order_by("asset")
    token = APIToken.objects.get(label=API_TOKEN_LABEL)

    return {
        "instance_setup_done": Instance.objects.filter(is_setup_done=True).exists(),
        "users": [
            {
                "email": user.email,
                "first_name": user.first_name,
                "is_active": user.is_active,
                "password_matches": user.check_password(password),
            }
            for user in users
        ],
        "workspaces": [
            {"slug": workspace.slug, "name": workspace.name, "owner": workspace.owner.email}
            for workspace in Workspace.objects.filter(slug__in=slugs).order_by("slug")
        ],
        "workspace_members": [
            [member.workspace.slug, member.member.email, member.role, member.is_active] for member in workspace_members
        ],
        "project": {
            "identifier": project.identifier,
            "name": project.name,
            "network": project.network,
            "lead": project.project_lead.email,
            "members": [
                [member.member.email, member.role]
                for member in ProjectMember.objects.filter(project=project).order_by("member__email")
            ],
        },
        "issues": [
            {
                "sequence_id": issue.sequence_id,
                "name": issue.name,
                "priority": issue.priority,
                "state": issue.state.name,
                "description_stripped": issue.description_stripped,
            }
            for issue in issues
        ],
        "comments": [
            {"html": comment.comment_html, "actor": comment.actor.email, "issue": comment.issue.name}
            for comment in comments
        ],
        "worklogs": [
            {
                "minutes": worklog.duration,
                "description": worklog.description,
                "logged_by": worklog.logged_by.email,
                "issue": worklog.issue.name,
            }
            for worklog in worklogs
        ],
        "attachments": [
            {
                "name": asset.attributes.get("name"),
                "size": asset.size,
                "is_uploaded": asset.is_uploaded,
                "stored_sha256": stored_object_sha256(asset.asset.name),
            }
            for asset in assets
        ],
        "expected_attachment_sha256": hashlib.sha256(ATTACHMENT_BYTES).hexdigest(),
        "api_token": {
            "owner": token.user.email,
            "workspace": token.workspace.slug,
            "is_active": token.is_active,
            "matches": token.token == api_token,
        },
    }


def main(argv):
    if argv not in (["--seed"], ["--verify"]):
        raise SystemExit("usage: compose_seed.py --seed | --verify")
    password = required_env("SEED_PASSWORD")
    api_token = required_env("SEED_API_TOKEN")
    setup_django()
    if argv == ["--seed"]:
        seed(password, api_token)
    result = fingerprint(password, api_token)
    sys.stdout.write(MARKER + json.dumps(result, sort_keys=True) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main(sys.argv[1:])
