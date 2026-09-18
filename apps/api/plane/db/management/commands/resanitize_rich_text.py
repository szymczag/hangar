# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Run stored rich text through the current HTML allowlist.

Content written before the allowlist checked attribute values, before page HTML
was sanitized at all, and activity rows copied from raw request bodies can still
hold markup the allowlist now removes. New writes are clean; this reaches the
rows that were already there.

    python manage.py resanitize_rich_text            # report only, writes nothing
    python manage.py resanitize_rich_text --apply    # rewrite the affected rows

A row is *affected* when sanitizing removes a tag or an attribute from it, or
changes an attribute value (a colour that is not a palette key, a style). Rows
whose only difference is serialization (quoting, entity spelling) are counted
separately and never rewritten: rewriting them changes nothing a reader sees and
would touch every row in the database.

Collaborative documents (description_binary) are not modified: rewriting a Yjs
document outside its session would give it a history the clients do not share.
The editor checks attribute values when it renders, so those documents are
covered at the point of display.
"""

from dataclasses import dataclass, field

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.db import transaction

from plane.db.models import (
    Description,
    DescriptionVersion,
    DraftIssue,
    Issue,
    IssueActivity,
    IssueComment,
    IssueDescriptionVersion,
    Module,
    Page,
    PageVersion,
    Project,
    Sticky,
)
from plane.utils.content_validator import validate_html_content

# (model, field, extra filter). Activity rows hold rich text only for these fields.
TARGETS = [
    (Issue, "description_html", {}),
    (IssueComment, "comment_html", {}),
    (DraftIssue, "description_html", {}),
    (Page, "description_html", {}),
    (PageVersion, "description_html", {}),
    (Sticky, "description_html", {}),
    (Description, "description_html", {}),
    (DescriptionVersion, "description_html", {}),
    (IssueDescriptionVersion, "description_html", {}),
    (Project, "description_html", {}),
    (Module, "description_html", {}),
    (IssueActivity, "old_value", {"field__in": ["comment", "description"]}),
    (IssueActivity, "new_value", {"field__in": ["comment", "description"]}),
]

SAMPLE_SIZE = 10


def _markup_signature(html):
    """Every element with its attributes and values, in document order."""
    soup = BeautifulSoup(html or "", "html.parser")
    return [
        (element.name, tuple(sorted((name, str(value)) for name, value in element.attrs.items())))
        for element in soup.find_all(True)
    ]


def classify(html):
    """(sanitized_html, affected) for one stored value."""
    is_valid, _, sanitized = validate_html_content(html)
    if not is_valid or sanitized is None:
        # Too large or unparseable: leave it alone and let the report name it.
        return None, False
    if sanitized == html:
        return sanitized, False
    return sanitized, _markup_signature(sanitized) != _markup_signature(html)


@dataclass
class Tally:
    scanned: int = 0
    affected: int = 0
    normalized_only: int = 0
    rejected: int = 0
    samples: list = field(default_factory=list)


class Command(BaseCommand):
    help = "Report (and with --apply, rewrite) stored rich text that the current HTML allowlist would change"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true", help="Rewrite affected rows. Without it nothing is written."
        )
        parser.add_argument("--batch-size", type=int, default=500)

    def handle(self, *args, **options):
        apply = options["apply"]
        batch_size = options["batch_size"]
        total_affected = 0

        for model, field_name, extra in TARGETS:
            tally = self._process(model, field_name, extra, apply, batch_size)
            total_affected += tally.affected
            label = f"{model.__name__}.{field_name}"
            self.stdout.write(
                f"{label}: scanned {tally.scanned}, affected {tally.affected}, "
                f"serialization only {tally.normalized_only}, not sanitizable {tally.rejected}"
            )
            if tally.samples:
                self.stdout.write(f"  affected ids (first {SAMPLE_SIZE}): {', '.join(tally.samples)}")

        verb = "rewritten" if apply else "would be rewritten (run with --apply)"
        self.stdout.write(self.style.SUCCESS(f"{total_affected} row(s) {verb}."))

    def _process(self, model, field_name, extra, apply, batch_size):
        tally = Tally()
        manager = getattr(model, "all_objects", model.objects)
        queryset = (
            manager.filter(**extra).exclude(**{f"{field_name}__isnull": True}).order_by("pk").only("pk", field_name)
        )

        last_pk = None
        while True:
            page = queryset if last_pk is None else queryset.filter(pk__gt=last_pk)
            rows = list(page[:batch_size])
            if not rows:
                return tally
            last_pk = rows[-1].pk

            changed = []
            for row in rows:
                value = getattr(row, field_name)
                # JSONField columns (Project, Module) hold an HTML string when set.
                if not isinstance(value, str) or not value:
                    continue
                tally.scanned += 1
                sanitized, affected = classify(value)
                if sanitized is None:
                    tally.rejected += 1
                elif affected:
                    tally.affected += 1
                    if len(tally.samples) < SAMPLE_SIZE:
                        tally.samples.append(str(row.pk))
                    setattr(row, field_name, sanitized)
                    changed.append(row)
                elif sanitized != value:
                    tally.normalized_only += 1

            if apply and changed:
                # bulk_update skips save(): no activity, version or notification
                # is produced for what is a correction of stored data.
                with transaction.atomic():
                    manager.bulk_update(changed, [field_name], batch_size=batch_size)
