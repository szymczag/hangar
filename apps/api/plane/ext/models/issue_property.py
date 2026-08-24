# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.conf import settings
from django.db import models
from django.db.models import Q

# Module imports
from plane.db.models.base import BaseModel


class PropertyTypeChoices(models.TextChoices):
    TEXT = "text", "Text"
    NUMBER = "number", "Number"
    DATE = "date", "Date"
    BOOLEAN = "boolean", "Boolean"
    SELECT = "select", "Select"
    MULTI_SELECT = "multi_select", "Multi select"
    MEMBER = "member", "Member"


class IssueProperty(BaseModel):
    """A custom field attached to an IssueType."""

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="ext_issue_properties")
    issue_type = models.ForeignKey("db.IssueType", on_delete=models.CASCADE, related_name="properties")
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    property_type = models.CharField(max_length=30, choices=PropertyTypeChoices.choices)
    is_multi = models.BooleanField(default=False)
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    default_value = models.JSONField(default=list, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    logo_props = models.JSONField(default=dict, blank=True)
    sort_order = models.FloatField(default=65535)

    class Meta:
        verbose_name = "Issue Property"
        verbose_name_plural = "Issue Properties"
        db_table = "ext_issue_properties"
        ordering = ("sort_order",)
        constraints = [
            models.UniqueConstraint(
                fields=["issue_type", "display_name"],
                condition=Q(deleted_at__isnull=True),
                name="ext_issue_property_unique_name_per_type",
            )
        ]
        indexes = [models.Index(fields=["issue_type"]), models.Index(fields=["workspace"])]

    def __str__(self):
        return f"{self.issue_type} / {self.display_name}"


class IssuePropertyOption(BaseModel):
    """An option of a select / multi_select property."""

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="ext_issue_property_options")
    property = models.ForeignKey(IssueProperty, on_delete=models.CASCADE, related_name="options")
    name = models.CharField(max_length=255)
    sort_order = models.FloatField(default=65535)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    logo_props = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Issue Property Option"
        verbose_name_plural = "Issue Property Options"
        db_table = "ext_issue_property_options"
        ordering = ("sort_order",)
        constraints = [
            models.UniqueConstraint(
                fields=["property", "name"],
                condition=Q(deleted_at__isnull=True),
                name="ext_issue_property_option_unique_name",
            )
        ]
        indexes = [models.Index(fields=["property"])]

    def __str__(self):
        return f"{self.property} / {self.name}"


class IssuePropertyValue(BaseModel):
    """One value row per issue/property; multi-valued types use multiple rows.

    Exactly one typed column is populated, matching property.property_type —
    enforced in the serializer/validator layer (a conditional DB constraint
    keyed on the parent's type is not expressible).
    """

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="ext_issue_property_values")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="ext_issue_property_values")
    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="property_values")
    property = models.ForeignKey(IssueProperty, on_delete=models.CASCADE, related_name="values")

    value_text = models.TextField(blank=True, null=True)
    value_number = models.DecimalField(max_digits=24, decimal_places=6, null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)
    value_date = models.DateTimeField(null=True, blank=True)
    value_option = models.ForeignKey(
        IssuePropertyOption, on_delete=models.CASCADE, null=True, blank=True, related_name="values"
    )
    value_member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="ext_property_values"
    )

    class Meta:
        verbose_name = "Issue Property Value"
        verbose_name_plural = "Issue Property Values"
        db_table = "ext_issue_property_values"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["issue", "property", "value_option"],
                condition=Q(deleted_at__isnull=True, value_option__isnull=False),
                name="ext_property_value_unique_option_row",
            ),
            models.UniqueConstraint(
                fields=["issue", "property", "value_member"],
                condition=Q(deleted_at__isnull=True, value_member__isnull=False),
                name="ext_property_value_unique_member_row",
            ),
        ]
        indexes = [
            models.Index(fields=["issue", "property"]),
            models.Index(fields=["property", "value_option"]),
            models.Index(fields=["property", "value_member"]),
        ]

    def __str__(self):
        return f"{self.issue_id} / {self.property_id}"
