# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
The idempotency key of a batched notification must not grow with the batch.

It used to be the notification ids joined together, which is 92 + 37N characters.
`EmailOutbox.idempotency_key` stops at 255, and the mailer refuses a longer one
before it gets there, so a batch of five updates to one work item for one
recipient reached 277 and was refused. Permanently: the parent rebuilds the same
batch from the same unprocessed rows on every run, so it failed identically every
five minutes. Four fitted and five did not, which made it look like a problem
with busy work items rather than with the key.

These tests pin the two properties that matters: the key is bounded whatever the
batch size, and it still identifies the same batch, because an idempotency key
that changed between runs would let a retry send a second copy.
"""

import uuid

import pytest

from plane.bgtasks.email_notification_task import notification_idempotency_key

# The column, and the check in front of it, in plane/mailer/service.py.
IDEMPOTENCY_KEY_LIMIT = 255


def _batch(size):
    return sorted(uuid.uuid4() for _ in range(size))


@pytest.mark.unit
class TestNotificationIdempotencyKey:
    @pytest.mark.parametrize("size", [1, 2, 4, 5, 6, 12, 22, 100, 500])
    def test_the_key_fits_whatever_the_batch_size(self, size):
        """5 is where the old format broke; 500 is where it would be absurd."""
        key = notification_idempotency_key(uuid.uuid4(), uuid.uuid4(), _batch(size))
        assert len(key) <= IDEMPOTENCY_KEY_LIMIT

    def test_the_length_does_not_depend_on_the_batch_at_all(self):
        issue_id, receiver_id = uuid.uuid4(), uuid.uuid4()
        lengths = {len(notification_idempotency_key(issue_id, receiver_id, _batch(n))) for n in (1, 5, 50, 500)}
        assert len(lengths) == 1, f"key length varies with batch size: {lengths}"

    def test_the_same_batch_keeps_the_same_key(self):
        """Otherwise a retry is a second copy rather than a no-op."""
        issue_id, receiver_id = uuid.uuid4(), uuid.uuid4()
        ids = _batch(7)
        assert notification_idempotency_key(issue_id, receiver_id, ids) == notification_idempotency_key(
            issue_id, receiver_id, list(ids)
        )

    def test_different_batches_get_different_keys(self):
        """Otherwise one notification suppresses another as a duplicate."""
        issue_id, receiver_id = uuid.uuid4(), uuid.uuid4()
        first = notification_idempotency_key(issue_id, receiver_id, _batch(3))
        second = notification_idempotency_key(issue_id, receiver_id, _batch(3))
        assert first != second

    def test_the_recipient_is_part_of_the_identity(self):
        """Two people notified about one work item must not collide."""
        issue_id = uuid.uuid4()
        ids = _batch(3)
        assert notification_idempotency_key(issue_id, uuid.uuid4(), ids) != notification_idempotency_key(
            issue_id, uuid.uuid4(), ids
        )

    def test_the_work_item_is_part_of_the_identity(self):
        receiver_id = uuid.uuid4()
        ids = _batch(3)
        assert notification_idempotency_key(uuid.uuid4(), receiver_id, ids) != notification_idempotency_key(
            uuid.uuid4(), receiver_id, ids
        )

    def test_the_key_stays_recognisable_in_the_ledger(self):
        """An operator reading the outbox should still see what kind of mail it is."""
        key = notification_idempotency_key(uuid.uuid4(), uuid.uuid4(), _batch(3))
        assert key.startswith("issue-notification:")

    def test_the_old_format_would_have_failed_this(self):
        """Guards the test itself: the limit has to be reachable to be worth pinning."""
        issue_id, receiver_id = uuid.uuid4(), uuid.uuid4()
        ids_str = "_".join(str(one) for one in _batch(5))
        legacy = f"issue-notification:{issue_id}:{receiver_id}:{ids_str}"
        assert len(legacy) > IDEMPOTENCY_KEY_LIMIT
