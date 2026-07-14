# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Outbound email configuration predicates shared by authentication surfaces."""

from django.conf import settings


def is_email_delivery_configured(smtp_host: str | None) -> bool:
    if settings.EMAIL_PROVIDER == "ses_api":
        return bool(settings.EMAIL_SES_REGION and settings.EMAIL_SES_CONFIGURATION_SET_AUTH)
    return bool(smtp_host)
