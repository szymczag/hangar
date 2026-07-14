# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
# Third party imports
from celery import shared_task
from django.db import OperationalError

# Third party imports
from django.template.loader import render_to_string


# Module imports
from plane.mailer.service import enqueue_rendered_email
from plane.utils.email import generate_plain_text_from_html
from plane.utils.exception_logger import log_exception
from plane.db.models import ProjectMember
from plane.db.models import User


@shared_task(autoretry_for=(OperationalError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def project_add_user_email(current_site, project_member_id, invitor_id):
    try:
        # Get the invitor
        invitor = User.objects.get(pk=invitor_id)
        inviter_first_name = invitor.first_name
        # Get the project member
        project_member = ProjectMember.objects.get(pk=project_member_id)
        # Get the project member details
        project_name = project_member.project.name
        workspace_name = project_member.workspace.name
        member_email = project_member.member.email
        project_url = f"{current_site}/{project_member.workspace.slug}/projects/{project_member.project_id}/issues"
        # set the context
        context = {
            "project_name": project_name,
            "workspace_name": workspace_name,
            "email": member_email,
            "inviter_first_name": inviter_first_name,
            "project_url": project_url,
        }

        # Set the subject
        subject = "You have been invited to a Hangar project"

        # Render the email template
        html_content = render_to_string("emails/notifications/project_addition.html", context)
        text_content = generate_plain_text_from_html(html_content)
        enqueue_rendered_email(
            recipient_email=member_email,
            recipient_user=project_member.member,
            template_key="project.member_added",
            subject=subject,
            text_body=text_content,
            html_body=html_content,
            idempotency_key=f"project-member-added:{project_member.id}",
        )
        return
    except Exception as e:
        log_exception(e)
        if isinstance(e, OperationalError):
            raise
        return
