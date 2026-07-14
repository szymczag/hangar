# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
# Third party imports
from celery import shared_task
from django.db import OperationalError

# Django imports
# Third party imports
from django.template.loader import render_to_string

# Module imports
from plane.db.models import Project, ProjectMemberInvite, User
from plane.mailer.service import enqueue_rendered_email
from plane.utils.email import generate_plain_text_from_html
from plane.utils.exception_logger import log_exception


@shared_task(autoretry_for=(OperationalError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def project_invitation(email, project_id, token, current_site, invitor):
    try:
        user = User.objects.get(email=invitor)
        project = Project.objects.get(pk=project_id)
        project_member_invite = ProjectMemberInvite.objects.get(token=token, email=email)

        relativelink = f"/project-invitations/?invitation_id={project_member_invite.id}&email={email}&slug={project.workspace.slug}&project_id={str(project_id)}"  # noqa: E501
        abs_url = current_site + relativelink

        subject = "You have a Hangar project invitation"

        context = {
            "email": email,
            "first_name": user.first_name,
            "project_name": project.name,
            "invitation_url": abs_url,
            "current_site": current_site,
        }

        html_content = render_to_string("emails/invitations/project_invitation.html", context)

        text_content = generate_plain_text_from_html(html_content)

        project_member_invite.message = text_content
        project_member_invite.save()

        recipient = User.objects.filter(email__iexact=email).first()
        enqueue_rendered_email(
            recipient_email=email,
            recipient_user=recipient,
            template_key="invitation.project_known" if recipient else "invitation.project",
            subject=subject,
            text_body=text_content,
            html_body=html_content,
            idempotency_key=f"project-invitation:{project_member_invite.id}",
        )
        return
    except (Project.DoesNotExist, ProjectMemberInvite.DoesNotExist):
        return
    except Exception as e:
        log_exception(e)
        if isinstance(e, OperationalError):
            raise
        return
