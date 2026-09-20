# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

# Third party imports
from celery import shared_task
from django.db.models import F
from django.template.loader import render_to_string

# Django imports
from django.utils import timezone

# Module imports
from plane.db.models import EmailNotificationLog, Issue, User
from plane.mailer.configuration import openpgp_subject_detail_enabled
from plane.mailer.enums import OutboxStatus
from plane.mailer.tokens import email_idempotency_token
from plane.mailer.service import enqueue_rendered_email
from plane.settings.redis import redis_instance
from plane.utils.host import app_base_url
from plane.utils.content_validator import sanitize_email_fragment
from plane.utils.email import generate_plain_text_from_html
from plane.utils.exception_logger import log_exception


def remove_unwanted_characters(input_text):
    # Remove only control characters and potentially problematic characters for email subjects
    processed_text = re.sub(r"[\x00-\x1F\x7F-\x9F]", "", input_text)
    return processed_text


# acquire and delete redis lock
def acquire_lock(lock_id, expire_time=300):
    redis_client = redis_instance()
    """Attempt to acquire a lock with a specified expiration time."""
    return redis_client.set(lock_id, "true", nx=True, ex=expire_time)


def release_lock(lock_id):
    """Release a lock."""
    redis_client = redis_instance()
    redis_client.delete(lock_id)


@shared_task
def stack_email_notification():
    # get all email notifications
    email_notifications = EmailNotificationLog.objects.filter(processed_at__isnull=True).order_by("receiver").values()

    # Create the below format for each of the issues
    # {"issue_id" : { "actor_id1": [ { data }, { data } ], "actor_id2": [ { data }, { data } ] }}

    # Convert to unique receivers list
    receivers = list(set([str(notification.get("receiver_id")) for notification in email_notifications]))
    # Loop through all the issues to create the emails
    for receiver_id in receivers:
        # Notification triggered for the receiver
        receiver_notifications = [
            notification for notification in email_notifications if str(notification.get("receiver_id")) == receiver_id
        ]
        # create payload for all issues
        payload = {}
        email_notification_ids_by_issue = {}
        for receiver_notification in receiver_notifications:
            issue_identifier = receiver_notification.get("entity_identifier")
            payload.setdefault(issue_identifier, {}).setdefault(
                str(receiver_notification.get("triggered_by_id")), []
            ).append(receiver_notification.get("data"))
            email_notification_ids_by_issue.setdefault(issue_identifier, []).append(receiver_notification.get("id"))

        # Create emails for all the issues
        for issue_id, notification_data in payload.items():
            send_email_notification.delay(
                issue_id=issue_id,
                notification_data=notification_data,
                receiver_id=receiver_id,
                email_notification_ids=email_notification_ids_by_issue.get(issue_id, []),
            )

    # Source rows remain unprocessed until a durable outbox row exists. Repeated
    # stack runs are safe because the child uses a stable idempotency key.


def create_payload(notification_data):
    # return format {"actor_id":  { "key": { "old_value": [], "new_value": [] } }}
    data = {}
    for actor_id, changes in notification_data.items():
        for change in changes:
            issue_activity = change.get("issue_activity")
            if issue_activity:  # Ensure issue_activity is not None
                field = issue_activity.get("field")
                old_value = str(issue_activity.get("old_value"))
                new_value = str(issue_activity.get("new_value"))

                # Append old_value if it's not empty and not already in the list
                if old_value:
                    (
                        data.setdefault(actor_id, {})
                        .setdefault(field, {})
                        .setdefault("old_value", [])
                        .append(old_value)
                        if old_value not in data.setdefault(actor_id, {}).setdefault(field, {}).get("old_value", [])
                        else None
                    )

                # Append new_value if it's not empty and not already in the list
                if new_value:
                    (
                        data.setdefault(actor_id, {})
                        .setdefault(field, {})
                        .setdefault("new_value", [])
                        .append(new_value)
                        if new_value not in data.setdefault(actor_id, {}).setdefault(field, {}).get("new_value", [])
                        else None
                    )

                if not data.get("actor_id", {}).get("activity_time", False):
                    data[actor_id]["activity_time"] = str(
                        datetime.fromisoformat(issue_activity.get("activity_time").rstrip("Z")).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    )

    return data


def process_mention(mention_component):
    soup = BeautifulSoup(mention_component, "html.parser")
    mentions = soup.find_all("mention-component")
    for mention in mentions:
        user_id = mention["entity_identifier"]
        user = User.objects.get(pk=user_id)
        user_name = user.display_name
        highlighted_name = f"@{user_name}"
        mention.replace_with(highlighted_name)
    return str(soup)


def notification_idempotency_key(issue_id, receiver_id, sorted_ids):
    """A key of fixed length, whatever the batch size.

    Joining the notification ids produced a key of 92 + 37N characters, and the
    outbox column -- like the check in front of it -- stops at 255. A batch of
    five updates to one work item for one recipient therefore reached 277 and was
    refused, permanently: the same batch is rebuilt from the same rows on every
    run, so it failed identically every five minutes. Four updates fit and five
    did not, which made it look like a problem with busy work items rather than
    with the key.

    The digest is over the same inputs in the same order, so a batch keeps the
    identity it had: re-running one cannot send a second copy.
    """
    return f"issue-notification:{email_idempotency_token('issue-notification', issue_id, receiver_id, *sorted_ids)}"


# An outer subject long enough to be cut off by a mail client says no more than
# a short one, and the header has a hard limit of its own.
MAX_OUTER_SUBJECT_TITLE = 120


def describe_notification(identifier, title, comment_actors):
    """A subject that says which work item changed, and how.

    Only ever used when an administrator has switched OPENPGP_SUBJECT_DETAIL on:
    this text travels in the clear, so it is a deliberate trade of confidentiality
    for an inbox someone can actually triage.
    """
    title = remove_unwanted_characters(str(title or "")).strip()
    if len(title) > MAX_OUTER_SUBJECT_TITLE:
        title = title[: MAX_OUTER_SUBJECT_TITLE - 1].rstrip() + "\u2026"
    described = f"{identifier} updates"
    if title:
        described = f"{described}: {title}"
    names = [name for name in (remove_unwanted_characters(str(a or "")).strip() for a in comment_actors) if name]
    if names:
        who = names[0] if len(names) == 1 else f"{names[0]} and {len(names) - 1} more"
        described = f"{described} - new comment from {who}"
    return described


def process_html_content(content):
    if content is None:
        return None
    processed_content_list = []
    for html_content in content:
        processed_content = sanitize_email_fragment(process_mention(html_content))
        processed_content_list.append(processed_content)
    return processed_content_list


def sanitize_comment_values(values):
    """Comment HTML is rendered into the e-mail with `|safe`. Activity rows
    written before the payload was sanitized still hold raw request HTML, so
    it is cleaned again here, for mail only."""
    if values is None:
        return None
    return [sanitize_email_fragment(value) for value in values]


# A row stays unprocessed until it is sent, and stack_email_notification re-picks
# every unprocessed row every five minutes. Without a ceiling, a permanently
# failing render -- an unparsable template, say -- is retried forever and reports
# nothing: the task swallows the exception and still returns success, so no
# task-failure alerting fires. Giving up after a few attempts stops the loop and
# leaves the reason on the row.
MAX_NOTIFICATION_ATTEMPTS = 5


def abandon_notifications(email_notification_ids, error):
    """Mark rows terminal immediately, for a failure no retry can clear."""

    try:
        detail = f"{type(error).__name__}: {error}"[:2000]
        EmailNotificationLog.objects.filter(pk__in=email_notification_ids, processed_at__isnull=True).update(
            processed_at=timezone.now(), attempts=F("attempts") + 1, last_error=detail
        )
    except Exception as bookkeeping_error:
        log_exception(bookkeeping_error)


def record_failed_attempt(email_notification_ids, error):
    """Count an attempt, and stop retrying once the ceiling is reached."""

    try:
        detail = f"{type(error).__name__}: {error}"[:2000]
        EmailNotificationLog.objects.filter(pk__in=email_notification_ids).update(
            attempts=F("attempts") + 1, last_error=detail
        )
        EmailNotificationLog.objects.filter(
            pk__in=email_notification_ids,
            processed_at__isnull=True,
            attempts__gte=MAX_NOTIFICATION_ATTEMPTS,
        ).update(processed_at=timezone.now())
    except Exception as bookkeeping_error:
        # Never let the bookkeeping mask the original failure.
        log_exception(bookkeeping_error)


@shared_task
def send_email_notification(issue_id, notification_data, receiver_id, email_notification_ids):
    # Convert UUIDs to a sorted, concatenated string
    sorted_ids = sorted(email_notification_ids)
    ids_str = "_".join(str(id) for id in sorted_ids)
    lock_id = f"send_email_notif_{issue_id}_{receiver_id}_{ids_str}"

    # acquire the lock for sending emails
    try:
        if acquire_lock(lock_id=lock_id):
            # The app origin used to arrive through a per-issue Redis key written
            # by the activity task. `base_host` derives it from settings and
            # ignores the request, so the key only ever held a constant -- while
            # its 600 second expiry, and Valkey being a cache with no persistence
            # guarantee, turned any restart or slow run into notifications that
            # were dropped without a row, a log line or an exception.
            base_api = app_base_url()

            data = create_payload(notification_data=notification_data)

            receiver = User.objects.get(pk=receiver_id)
            issue = Issue.objects.get(pk=issue_id)
            template_data = []
            total_changes = 0
            comments = []
            actors_involved = []
            for actor_id, changes in data.items():
                actor = User.objects.get(pk=actor_id)
                total_changes = total_changes + len(changes)
                comment = changes.pop("comment", False)
                mention = changes.pop("mention", False)
                actors_involved.append(actor_id)
                if comment:
                    comment["new_value"] = sanitize_comment_values(comment.get("new_value"))
                    comment["old_value"] = sanitize_comment_values(comment.get("old_value"))
                    comments.append(
                        {
                            "actor_comments": comment,
                            "actor_detail": {
                                "avatar_url": f"{base_api}{actor.avatar_url}",
                                "first_name": actor.first_name,
                                "last_name": actor.last_name,
                            },
                        }
                    )
                if mention:
                    mention["new_value"] = process_html_content(mention.get("new_value"))
                    mention["old_value"] = process_html_content(mention.get("old_value"))
                    comments.append(
                        {
                            "actor_comments": mention,
                            "actor_detail": {
                                "avatar_url": f"{base_api}{actor.avatar_url}",
                                "first_name": actor.first_name,
                                "last_name": actor.last_name,
                            },
                        }
                    )
                activity_time = changes.pop("activity_time")
                # Parse the input string into a datetime object
                formatted_time = datetime.strptime(activity_time, "%Y-%m-%d %H:%M:%S").strftime("%H:%M %p")

                if changes:
                    template_data.append(
                        {
                            "actor_detail": {
                                "avatar_url": f"{base_api}{actor.avatar_url}",
                                "first_name": actor.first_name,
                                "last_name": actor.last_name,
                            },
                            "changes": changes,
                            "issue_details": {
                                "name": issue.name,
                                "identifier": f"{issue.project.identifier}-{issue.sequence_id}",
                            },
                            "activity_time": str(formatted_time),
                        }
                    )

            summary = "Updates were made to the issue by"

            # Send the mail
            identifier = f"{issue.project.identifier}-{issue.sequence_id}"
            subject = f"{identifier} {remove_unwanted_characters(issue.name)}"
            # The outer subject is generic unless an administrator opted in.
            outer_subject = ""
            if openpgp_subject_detail_enabled():
                outer_subject = describe_notification(
                    identifier,
                    issue.name,
                    [
                        f"{c['actor_detail']['first_name']} {c['actor_detail']['last_name']}".strip()
                        for c in comments
                    ],
                )
            context = {
                "data": template_data,
                "summary": summary,
                "actors_involved": len(set(actors_involved)),
                "issue": {
                    "issue_identifier": f"{str(issue.project.identifier)}-{str(issue.sequence_id)}",
                    "name": issue.name,
                    "issue_url": f"{base_api}/{str(issue.project.workspace.slug)}/projects/{str(issue.project.id)}/issues/{str(issue.id)}",  # noqa: E501
                },
                "receiver": {"email": receiver.email},
                "issue_url": f"{base_api}/{str(issue.project.workspace.slug)}/projects/{str(issue.project.id)}/issues/{str(issue.id)}",  # noqa: E501
                "project_url": f"{base_api}/{str(issue.project.workspace.slug)}/projects/{str(issue.project.id)}/issues/",  # noqa: E501
                "workspace": str(issue.project.workspace.slug),
                "project": str(issue.project.name),
                "user_preference": f"{base_api}/{str(issue.project.workspace.slug)}/settings/account/notifications/",
                "comments": comments,
                "entity_type": "issue",
            }
            try:
                html_content = render_to_string("emails/notifications/issue-updates.html", context)
                text_content = generate_plain_text_from_html(html_content)

                result = enqueue_rendered_email(
                    recipient_email=receiver.email,
                    recipient_user=receiver,
                    template_key="notification.issue_updates",
                    subject=subject,
                    text_body=text_content,
                    html_body=html_content,
                    idempotency_key=notification_idempotency_key(issue_id, receiver_id, sorted_ids),
                    outer_subject=outer_subject,
                )
                updates = {"processed_at": timezone.now()}
                if result.outbox_id:
                    updates["outbox_id"] = result.outbox_id
                if result.status == OutboxStatus.ACCEPTED:
                    updates["sent_at"] = timezone.now()
                EmailNotificationLog.objects.filter(pk__in=email_notification_ids).update(**updates)

                # release the lock
                release_lock(lock_id=lock_id)
                return
            except Exception as e:
                log_exception(e)
                record_failed_attempt(email_notification_ids, e)
                # release the lock
                release_lock(lock_id=lock_id)
                return
        else:
            logging.getLogger("plane.worker").info("Duplicate email received skipping")
            return
    except (Issue.DoesNotExist, User.DoesNotExist) as e:
        # The work item or the recipient is gone. No later run can render this
        # notification, so retrying it every five minutes forever only keeps a
        # row alive that nothing will ever send.
        log_exception(e)
        abandon_notifications(email_notification_ids, e)
        release_lock(lock_id=lock_id)
        return
    except Exception as e:
        # Anything unexpected -- a misconfigured base URL among them -- is
        # counted rather than swallowed, so a permanent failure reaches a
        # terminal state instead of retrying in silence.
        log_exception(e)
        record_failed_attempt(email_notification_ids, e)
        release_lock(lock_id=lock_id)
        return
