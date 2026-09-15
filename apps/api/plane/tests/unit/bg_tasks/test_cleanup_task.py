# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Unit tests for the log cleanup tasks.

Verifies that API activity logs past the retention window are hard-deleted
(removed from PostgreSQL, not soft-deleted) and that fresh logs are retained.
"""

from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from uuid import uuid4

from plane.bgtasks.cleanup_task import (
    delete_api_logs,
    delete_email_notification_logs,
    delete_webhook_logs,
    process_cleanup_task,
)
from plane.bgtasks.email_notification_task import MAX_NOTIFICATION_ATTEMPTS
from plane.db.models import APIActivityLog, EmailNotificationLog, WebhookLog
from plane.tests.factories import UserFactory, WorkspaceFactory


def _make_api_log(created_at):
    log = APIActivityLog.objects.create(
        token_identifier="hashed-token",
        path="/api/v1/workspaces/",
        method="GET",
        response_code=200,
    )
    # created_at is auto-set on insert, so backdate it explicitly afterwards.
    APIActivityLog.all_objects.filter(pk=log.pk).update(created_at=created_at)
    return log


def _make_webhook_log(workspace, created_at):
    log = WebhookLog.objects.create(
        workspace=workspace,
        webhook=uuid4(),
        event_type="issue",
        request_method="POST",
        response_status="200",
    )
    WebhookLog.all_objects.filter(pk=log.pk).update(created_at=created_at)
    return log


def _make_email_log(user, sent_at):
    return EmailNotificationLog.objects.create(
        receiver=user,
        triggered_by=user,
        entity_name="issue",
        entity="issue",
        sent_at=sent_at,
    )


@pytest.mark.unit
@pytest.mark.django_db
class TestDeleteApiLogs:
    def test_expired_logs_are_hard_deleted(self):
        retention_days = settings.API_ACTIVITY_LOG_RETENTION_DAYS
        expired = _make_api_log(timezone.now() - timedelta(days=retention_days + 1))

        delete_api_logs()

        # Hard delete: the row must be gone even from the unfiltered manager.
        assert not APIActivityLog.all_objects.filter(pk=expired.pk).exists()

    def test_recent_logs_are_retained(self):
        retention_days = settings.API_ACTIVITY_LOG_RETENTION_DAYS
        recent = _make_api_log(timezone.now() - timedelta(days=retention_days - 1))

        delete_api_logs()

        assert APIActivityLog.all_objects.filter(pk=recent.pk).exists()


@pytest.mark.unit
@pytest.mark.django_db
class TestDeleteWebhookLogs:
    def test_expired_logs_are_hard_deleted(self):
        workspace = WorkspaceFactory()
        retention_days = settings.WEBHOOK_LOG_RETENTION_DAYS
        expired = _make_webhook_log(workspace, timezone.now() - timedelta(days=retention_days + 1))

        delete_webhook_logs()

        assert not WebhookLog.all_objects.filter(pk=expired.pk).exists()

    def test_recent_logs_are_retained(self):
        workspace = WorkspaceFactory()
        retention_days = settings.WEBHOOK_LOG_RETENTION_DAYS
        recent = _make_webhook_log(workspace, timezone.now() - timedelta(days=retention_days - 1))

        delete_webhook_logs()

        assert WebhookLog.all_objects.filter(pk=recent.pk).exists()


@pytest.mark.unit
@pytest.mark.django_db
class TestDeleteEmailLogs:
    def test_expired_logs_are_hard_deleted(self):
        user = UserFactory()
        retention_days = settings.EMAIL_LOG_RETENTION_DAYS
        expired = _make_email_log(user, timezone.now() - timedelta(days=retention_days + 1))

        delete_email_notification_logs()

        assert not EmailNotificationLog.all_objects.filter(pk=expired.pk).exists()

    def test_recent_logs_are_retained(self):
        user = UserFactory()
        retention_days = settings.EMAIL_LOG_RETENTION_DAYS
        recent = _make_email_log(user, timezone.now() - timedelta(days=retention_days - 1))

        delete_email_notification_logs()

        assert EmailNotificationLog.all_objects.filter(pk=recent.pk).exists()

    def test_a_notification_still_waiting_to_send_is_never_deleted(self):
        """However old it is. Deleting it would silently drop the notification."""
        user = UserFactory()
        retention_days = settings.EMAIL_LOG_RETENTION_DAYS
        pending = _make_email_log(user, None)
        EmailNotificationLog.all_objects.filter(pk=pending.pk).update(
            created_at=timezone.now() - timedelta(days=retention_days + 30)
        )

        delete_email_notification_logs()

        assert EmailNotificationLog.all_objects.filter(pk=pending.pk).exists()

    def test_a_notification_that_gave_up_is_reaped(self):
        """Terminally failed rows used to be immortal: `sent_at` stays NULL and
        SQL `NULL <= cutoff` never matches, so nothing ever collected them."""
        user = UserFactory()
        retention_days = settings.EMAIL_LOG_RETENTION_DAYS
        failed = _make_email_log(user, None)
        EmailNotificationLog.all_objects.filter(pk=failed.pk).update(
            processed_at=timezone.now() - timedelta(days=retention_days + 1),
            attempts=MAX_NOTIFICATION_ATTEMPTS,
            last_error="TemplateSyntaxError: Invalid block tag",
        )

        delete_email_notification_logs()

        assert not EmailNotificationLog.all_objects.filter(pk=failed.pk).exists()


@pytest.mark.unit
class TestProcessCleanupTaskErrorHandling:
    def test_batch_delete_failure_is_swallowed(self):
        """A failing batch is logged and skipped; the run does not raise."""

        class _BoomManager:
            @staticmethod
            def filter(**kwargs):
                raise RuntimeError("db unavailable")

        class _BoomModel:
            all_objects = _BoomManager()

        # Should not raise even though the delete blows up.
        process_cleanup_task(lambda: iter([1, 2, 3]), _BoomModel, "Boom")
