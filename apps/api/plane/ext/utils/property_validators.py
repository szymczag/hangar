# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Per-type validation/coercion for custom property values.

Values arrive from the client as lists of strings keyed by property id
(the bundle shape the web issue-modal provider produces). Each validator
returns the kwargs for one IssuePropertyValue row or raises ValidationError.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.exceptions import ValidationError

from plane.db.models import ProjectMember

from plane.ext.models import IssueProperty, IssuePropertyOption, PropertyTypeChoices


def _validate_text(prop, raw, _project_id):
    return {"value_text": str(raw)}


def _validate_number(prop, raw, _project_id):
    try:
        return {"value_number": Decimal(str(raw))}
    except (InvalidOperation, ValueError):
        raise ValidationError({prop.display_name: f"'{raw}' is not a valid number"})


def _validate_boolean(prop, raw, _project_id):
    normalized = str(raw).strip().lower()
    if normalized in ("true", "1"):
        return {"value_boolean": True}
    if normalized in ("false", "0"):
        return {"value_boolean": False}
    raise ValidationError({prop.display_name: f"'{raw}' is not a valid boolean"})


def _validate_date(prop, raw, _project_id):
    parsed = parse_datetime(str(raw))
    if parsed is None:
        date_only = parse_date(str(raw))
        if date_only is not None:
            parsed = datetime(date_only.year, date_only.month, date_only.day)
    if parsed is None:
        raise ValidationError({prop.display_name: f"'{raw}' is not a valid date"})
    return {"value_date": parsed}


def _validate_option(prop, raw, _project_id):
    # The option must belong to this exact property — a foreign option id is
    # either a client bug or a cross-tenant probe.
    option = IssuePropertyOption.objects.filter(property=prop, pk=raw, is_active=True).first()
    if option is None:
        raise ValidationError({prop.display_name: "Invalid option"})
    return {"value_option": option}


def _validate_member(prop, raw, project_id):
    # Members must belong to the issue's project — never accept arbitrary
    # user ids (cross-tenant user enumeration / assignment).
    is_member = ProjectMember.objects.filter(project_id=project_id, member_id=raw, is_active=True).exists()
    if not is_member:
        raise ValidationError({prop.display_name: "User is not a member of this project"})
    return {"value_member_id": raw}


VALIDATORS = {
    PropertyTypeChoices.TEXT: _validate_text,
    PropertyTypeChoices.NUMBER: _validate_number,
    PropertyTypeChoices.BOOLEAN: _validate_boolean,
    PropertyTypeChoices.DATE: _validate_date,
    PropertyTypeChoices.SELECT: _validate_option,
    PropertyTypeChoices.MULTI_SELECT: _validate_option,
    PropertyTypeChoices.MEMBER: _validate_member,
}

MULTI_VALUE_TYPES = {PropertyTypeChoices.MULTI_SELECT, PropertyTypeChoices.MEMBER}


def validate_property_values(prop: IssueProperty, raw_values: list, project_id) -> list[dict]:
    """Validate the raw string values for one property.

    Returns a list of row kwargs for IssuePropertyValue creation.
    """
    if not isinstance(raw_values, list):
        raise ValidationError({prop.display_name: "Values must be a list"})

    values = [v for v in raw_values if v not in (None, "")]

    if prop.is_required and not values:
        raise ValidationError({prop.display_name: "This property is required"})

    is_multi = prop.property_type in MULTI_VALUE_TYPES and prop.is_multi
    if not is_multi and len(values) > 1:
        raise ValidationError({prop.display_name: "Multiple values are not allowed"})

    validator = VALIDATORS[prop.property_type]
    rows = []
    seen = set()
    for raw in values:
        key = str(raw)
        if key in seen:
            continue
        seen.add(key)
        rows.append(validator(prop, raw, project_id))
    return rows
