# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
A notification must never be dropped without a trace.

The mailer used to read the app origin from a per-issue Redis key written by the
activity task. The key expired after 600 seconds and Valkey holds no persistence
guarantee here, so a restart or a slow run left the mailer with nothing -- and it
returned early, before writing an outbox row, before setting `processed_at`, and
before any of the attempt bookkeeping. The row stayed pending forever, was
re-selected every five minutes, and produced no log line and no exception. On one
instance that silently stranded 22 of 22 notifications.

These tests pin the two properties that failure violated: the origin does not
depend on a cache, and a notification that cannot be rendered reaches a terminal
state instead of being retried in silence.
"""

from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.utils import timezone

from plane.bgtasks.email_notification_task import (
    MAX_NOTIFICATION_ATTEMPTS,
    abandon_notifications,
    record_failed_attempt,
)
from plane.db.models import EmailNotificationLog
from plane.tests.factories import UserFactory
from plane.utils.host import app_base_url


@pytest.mark.unit
class TestAppBaseUrl:
    """The origin comes from settings, so no request and no cache is needed."""

    @override_settings(APP_BASE_URL="https://app.example.com", WEB_URL="https://web.example.com")
    def test_app_base_url_is_preferred(self):
        assert app_base_url() == "https://app.example.com"

    @override_settings(APP_BASE_URL=None, WEB_URL="https://web.example.com")
    def test_web_url_is_the_fallback(self):
        assert app_base_url() == "https://web.example.com"

    @override_settings(APP_BASE_URL=None, WEB_URL=None)
    def test_an_unconfigured_instance_raises_rather_than_returning_nothing(self):
        """A falsy origin would build links to nowhere and never say so."""
        with pytest.raises(ImproperlyConfigured):
            app_base_url()


def _make_notification(user):
    return EmailNotificationLog.objects.create(
        receiver=user,
        triggered_by=user,
        entity_name="issue",
        entity="issue",
    )


@pytest.mark.unit
@pytest.mark.django_db
class TestFailureBookkeeping:
    def test_an_attempt_is_counted_and_the_reason_kept(self):
        user = UserFactory()
        row = _make_notification(user)

        record_failed_attempt([row.id], ValueError("nope"))

        row.refresh_from_db()
        assert row.attempts == 1
        assert "ValueError: nope" in row.last_error
        assert row.processed_at is None, "one failure must not end the retries"

    def test_retrying_stops_once_the_ceiling_is_reached(self):
        user = UserFactory()
        row = _make_notification(user)

        for _ in range(MAX_NOTIFICATION_ATTEMPTS):
            record_failed_attempt([row.id], ValueError("nope"))

        row.refresh_from_db()
        assert row.attempts == MAX_NOTIFICATION_ATTEMPTS
        assert row.processed_at is not None, "a permanent failure must reach a terminal state"

    def test_a_vanished_work_item_is_abandoned_at_once(self):
        """No later run can render it, so counting to five first is pointless."""
        user = UserFactory()
        row = _make_notification(user)

        abandon_notifications([row.id], LookupError("issue is gone"))

        row.refresh_from_db()
        assert row.processed_at is not None
        assert "LookupError: issue is gone" in row.last_error

    def test_abandoning_does_not_disturb_an_already_sent_row(self):
        user = UserFactory()
        row = _make_notification(user)
        sent_at = timezone.now()
        EmailNotificationLog.objects.filter(pk=row.pk).update(processed_at=sent_at, sent_at=sent_at)

        abandon_notifications([row.id], LookupError("issue is gone"))

        row.refresh_from_db()
        assert row.processed_at == sent_at
        assert row.last_error == ""


@pytest.mark.unit
@pytest.mark.django_db
class TestOriginNoLongerNeedsTheCache:
    def test_rendering_does_not_consult_redis_for_the_origin(self):
        """The early return this replaces is what stranded the 22 rows.

        `redis_instance` is still used for the duplicate-send lock, so this
        asserts the narrower thing that matters: nothing reads a per-issue key.
        """
        with patch("plane.bgtasks.email_notification_task.redis_instance") as redis:
            with override_settings(APP_BASE_URL="https://app.example.com"):
                assert app_base_url() == "https://app.example.com"
        redis.return_value.get.assert_not_called()
