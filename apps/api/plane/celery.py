# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os
import logging
from datetime import timedelta

# Third party imports
from celery import Celery
from pythonjsonlogger.json import JsonFormatter
from celery.signals import after_setup_logger, after_setup_task_logger
from celery.schedules import crontab, schedule

# Module imports
from plane.settings.redis import redis_instance

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plane.settings.production")

ri = redis_instance()


# Configurable metrics push interval (in minutes)
# Default: 360 (6 hours), set to 5 for development/testing
def _get_metrics_push_interval_minutes() -> int:
    raw = os.environ.get("METRICS_PUSH_INTERVAL_MINUTES", "360")
    try:
        value = int(raw)
        # Cap at 10,000,000 minutes to prevent timedelta(minutes=...) OverflowError
        # on arbitrarily large inputs while still allowing multi-year intervals.
        return value if 0 < value <= 10_000_000 else 360
    except (ValueError, OverflowError):
        return 360


METRICS_PUSH_INTERVAL_MINUTES = _get_metrics_push_interval_minutes()

app = Celery("plane")

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Producer tasks must be confirmed by RabbitMQ or fail back to their caller.
# Once an EmailOutbox row exists, the database dispatcher is the durable
# recovery path and no longer depends on a single broker publication.
app.conf.task_publish_retry = True
app.conf.task_publish_retry_policy = {
    "max_retries": 5,
    "interval_start": 0.2,
    "interval_step": 0.5,
    "interval_max": 2,
}
app.conf.broker_transport_options = {
    **(app.conf.broker_transport_options or {}),
    "confirm_publish": True,
}

# Mail delivery and provider feedback use a dedicated queue so production can
# attach a narrowly scoped AWS identity only to the mail worker.
app.conf.task_routes = {
    "plane.bgtasks.email_delivery_task.*": {"queue": "email"},
    "plane.ext.tasks.run_todoist_import": {"queue": "imports"},
}

app.conf.beat_schedule = {
    # Intra day recurring jobs
    "check-every-five-minutes-to-send-email-notifications": {
        "task": "plane.bgtasks.email_notification_task.stack_email_notification",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "recover-stale-secure-email-outbox": {
        "task": "plane.bgtasks.email_delivery_task.recover_stale_email_outbox",
        "schedule": crontab(minute="*/2"),
    },
    "dispatch-due-secure-email-outbox": {
        "task": "plane.bgtasks.email_delivery_task.dispatch_due_email_outbox",
        "schedule": crontab(minute="*"),
    },
    "expire-openpgp-keys": {
        "task": "plane.bgtasks.email_delivery_task.expire_openpgp_keys",
        "schedule": crontab(minute=15),
    },
    "consume-ses-email-events": {
        "task": "plane.bgtasks.email_delivery_task.consume_ses_email_events",
        "schedule": crontab(minute="*"),
    },
    "push-instance-metrics": {
        "task": "plane.license.bgtasks.telemetry_metrics.push_instance_metrics",
        "schedule": schedule(run_every=timedelta(minutes=METRICS_PUSH_INTERVAL_MINUTES)),
    },
    # Occurs once every day
    "check-every-day-to-delete-hard-delete": {
        "task": "plane.bgtasks.deletion_task.hard_delete",
        "schedule": crontab(hour=0, minute=0),  # UTC 00:00
    },
    "check-every-day-to-archive-and-close": {
        "task": "plane.bgtasks.issue_automation_task.archive_and_close_old_issues",
        "schedule": crontab(hour=1, minute=0),  # UTC 01:00
    },
    "check-every-day-to-delete_exporter_history": {
        "task": "plane.bgtasks.exporter_expired_task.delete_old_s3_link",
        "schedule": crontab(hour=1, minute=30),  # UTC 01:30
    },
    "check-every-hour-to-delete-file-asset": {
        "task": "plane.bgtasks.file_asset_task.delete_unuploaded_file_asset",
        "schedule": crontab(minute=20),  # Every hour
    },
    "check-every-day-to-delete-api-logs": {
        "task": "plane.bgtasks.cleanup_task.delete_api_logs",
        "schedule": crontab(hour=2, minute=30),  # UTC 02:30
    },
    "check-every-day-to-delete-email-notification-logs": {
        "task": "plane.bgtasks.cleanup_task.delete_email_notification_logs",
        "schedule": crontab(hour=2, minute=45),  # UTC 02:45
    },
    "check-every-day-to-delete-secure-email-records": {
        "task": "plane.bgtasks.email_delivery_task.cleanup_secure_email_records",
        "schedule": crontab(hour=2, minute=50),
    },
    "check-every-day-to-delete-page-versions": {
        "task": "plane.bgtasks.cleanup_task.delete_page_versions",
        "schedule": crontab(hour=3, minute=0),  # UTC 03:00
    },
    "check-every-day-to-delete-issue-description-versions": {
        "task": "plane.bgtasks.cleanup_task.delete_issue_description_versions",
        "schedule": crontab(hour=3, minute=15),  # UTC 03:15
    },
    "check-every-day-to-delete-webhook-logs": {
        "task": "plane.bgtasks.cleanup_task.delete_webhook_logs",
        "schedule": crontab(hour=3, minute=30),  # UTC 03:30
    },
    "check-every-day-to-delete-exporter-history": {
        "task": "plane.bgtasks.exporter_expired_task.delete_old_s3_link",
        "schedule": crontab(hour=3, minute=45),  # UTC 03:45
    },
    "reconcile-expired-import-sources": {
        "task": "plane.ext.tasks.cleanup_import_sources",
        "schedule": 300.0,
    },
    "dispatch-pending-todoist-imports": {
        "task": "plane.ext.tasks.dispatch_pending_imports",
        "schedule": 30.0,
    },
    "recover-expired-todoist-import-leases": {
        "task": "plane.ext.tasks.recover_expired_import_leases",
        "schedule": 30.0,
    },
}


# Setup logging
@after_setup_logger.connect
def setup_loggers(logger, *args, **kwargs):
    formatter = JsonFormatter('"%(levelname)s %(asctime)s %(module)s %(name)s %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(fmt=formatter)
    logger.addHandler(handler)


@after_setup_task_logger.connect
def setup_task_loggers(logger, *args, **kwargs):
    formatter = JsonFormatter('"%(levelname)s %(asctime)s %(module)s %(name)s %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(fmt=formatter)
    logger.addHandler(handler)


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

app.conf.beat_scheduler = "django_celery_beat.schedulers.DatabaseScheduler"
