# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
# Third party imports
from celery import shared_task
from django.db import OperationalError

# Django imports
from django.template.loader import render_to_string

# Module imports
from plane.db.models import User, Workspace, WorkspaceMemberInvite
from plane.mailer.service import enqueue_rendered_email
from plane.utils.email import generate_plain_text_from_html
from plane.utils.exception_logger import log_exception


@shared_task(autoretry_for=(OperationalError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def workspace_invitation(email, workspace_id, token, current_site, inviter):
    try:
        user = User.objects.get(email=inviter)

        workspace = Workspace.objects.get(pk=workspace_id)
        workspace_member_invite = WorkspaceMemberInvite.objects.get(token=token, email=email)

        # Relative link
        relative_link = (
            f"/workspace-invitations/?invitation_id={workspace_member_invite.id}&slug={workspace.slug}&token={token}"  # noqa: E501
        )

        # The complete url including the domain
        abs_url = str(current_site) + relative_link

        subject = "You have a Hangar workspace invitation"

        context = {
            "email": email,
            "first_name": user.first_name or user.display_name or user.email,
            "workspace_name": workspace.name,
            "abs_url": abs_url,
        }

        html_content = render_to_string("emails/invitations/workspace_invitation.html", context)

        text_content = generate_plain_text_from_html(html_content)

        workspace_member_invite.message = text_content
        workspace_member_invite.save()

        recipient = User.objects.filter(email__iexact=email).first()
        enqueue_rendered_email(
            recipient_email=email,
            recipient_user=recipient,
            template_key="invitation.workspace_known" if recipient else "invitation.workspace",
            subject=subject,
            text_body=text_content,
            html_body=html_content,
            idempotency_key=f"workspace-invitation:{workspace_member_invite.id}",
        )
        return
    except (Workspace.DoesNotExist, WorkspaceMemberInvite.DoesNotExist):
        return
    except Exception as e:
        log_exception(e)
        if isinstance(e, OperationalError):
            raise
        return
