# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Outbound email configuration predicates shared by authentication surfaces."""

import os

from django.conf import settings

from plane.license.utils.instance_value import get_configuration_value


def is_email_delivery_configured(smtp_host: str | None) -> bool:
    if settings.EMAIL_PROVIDER == "ses_api":
        return bool(settings.EMAIL_SES_REGION and settings.EMAIL_SES_CONFIGURATION_SET_AUTH)
    return bool(smtp_host)


def openpgp_subject_detail_enabled() -> bool:
    """Whether an encrypted notification may describe itself in its Subject.

    The outer subject is the one header encryption cannot cover, so this stays
    off unless an administrator turns it on in God Mode. A lookup failure is
    treated as off: the safe answer is the one that reveals nothing.
    """
    try:
        (raw_setting,) = get_configuration_value(
            [{"key": "OPENPGP_SUBJECT_DETAIL", "default": os.environ.get("OPENPGP_SUBJECT_DETAIL", "0")}]
        )
    except Exception:
        return False
    return str(raw_setting or "").strip() == "1"
