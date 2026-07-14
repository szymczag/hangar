# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import csv
from io import StringIO

import pytest

from plane.ext.utils.importers.todoist_csv import (
    MAX_FILE_BYTES,
    TodoistImportParseError,
    parse_todoist_csv,
)


HEADERS = [
    "TYPE",
    "CONTENT",
    "DESCRIPTION",
    "IS_COLLAPSED",
    "PRIORITY",
    "INDENT",
    "AUTHOR",
    "RESPONSIBLE",
    "DATE",
    "DATE_LANG",
    "TIMEZONE",
    "DURATION",
    "DURATION_UNIT",
    "DEADLINE",
    "DEADLINE_LANG",
]


def make_csv(*rows: dict[str, str], bom: bool = False) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=HEADERS)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    encoded = output.getvalue().encode()
    return b"\xef\xbb\xbf" + encoded if bom else encoded


@pytest.mark.unit
class TestTodoistCsvParser:
    def test_parses_supported_rows_and_hierarchy(self):
        preview = parse_todoist_csv(
            make_csv(
                {"TYPE": "meta", "CONTENT": "view_style=list"},
                {"TYPE": "project_note", "CONTENT": "Project context"},
                {"TYPE": "section", "CONTENT": "Preparation"},
                {
                    "TYPE": "task",
                    "CONTENT": "Parent task",
                    "DESCRIPTION": "A **safe** description",
                    "PRIORITY": "1",
                    "INDENT": "1",
                    "RESPONSIBLE": "Project Owner (100)",
                    "DATE": "2026-07-20",
                    "DEADLINE": "2026-07-25",
                },
                {"TYPE": "note", "CONTENT": "First comment"},
                {"TYPE": "note", "CONTENT": "Second comment"},
                {"TYPE": "task", "CONTENT": "Child task", "PRIORITY": "4", "INDENT": "2"},
                {},
            )
        )

        assert preview.counts == {
            "meta": 1,
            "project_note": 1,
            "section": 1,
            "task": 2,
            "note": 2,
            "blank": 1,
            "rows": 8,
            "failed": 0,
            "importable": 6,
        }
        assert preview.assignees == ("Project Owner (100)",)
        parent = next(record for record in preview.records if record.content == "Parent task")
        child = next(record for record in preview.records if record.content == "Child task")
        notes = [record for record in preview.records if record.kind == "note"]
        assert parent.priority == "urgent"
        assert parent.scheduled_date.isoformat() == "2026-07-20"
        assert parent.deadline.isoformat() == "2026-07-25"
        assert child.parent_row == parent.row
        assert child.section_row == parent.section_row
        assert all(note.task_row == parent.row for note in notes)

    def test_accepts_utf8_bom_unicode_and_multiline_content(self):
        preview = parse_todoist_csv(
            make_csv(
                {
                    "TYPE": "task",
                    "CONTENT": "Zażółć gęślą",
                    "DESCRIPTION": "Line one, with a comma\nLine two",
                    "PRIORITY": "4",
                    "INDENT": "1",
                },
                bom=True,
            )
        )

        assert preview.records[0].content == "Zażółć gęślą"
        assert preview.records[0].description == "Line one, with a comma\nLine two"

    def test_records_recoverable_row_errors(self):
        preview = parse_todoist_csv(
            make_csv(
                {"TYPE": "note", "CONTENT": "Orphan"},
                {"TYPE": "task", "CONTENT": "Bad priority", "PRIORITY": "9", "INDENT": "1"},
                {"TYPE": "task", "CONTENT": "Missing parent", "PRIORITY": "4", "INDENT": "2"},
                {"TYPE": "unsupported", "CONTENT": "Unknown"},
                {"TYPE": "task", "CONTENT": "Valid", "PRIORITY": "4", "INDENT": "1"},
            )
        )

        assert [diagnostic.code for diagnostic in preview.errors] == [
            "orphan_note",
            "invalid_priority",
            "invalid_hierarchy",
            "unsupported_row_type",
        ]
        assert preview.counts["failed"] == 4
        assert [record.content for record in preview.records] == ["Valid"]

    def test_warns_without_guessing_recurring_schedule(self):
        preview = parse_todoist_csv(
            make_csv(
                {
                    "TYPE": "task",
                    "CONTENT": "Recurring task",
                    "PRIORITY": "4",
                    "INDENT": "1",
                    "DATE": "every Monday",
                }
            )
        )

        assert preview.records[0].scheduled_date is None
        assert preview.records[0].unsupported_schedule == "every Monday"
        assert [warning.code for warning in preview.warnings] == ["unsupported_schedule"]

    def test_rejects_task_with_invalid_calendar_date(self):
        preview = parse_todoist_csv(
            make_csv(
                {
                    "TYPE": "task",
                    "CONTENT": "Invalid date",
                    "PRIORITY": "4",
                    "INDENT": "1",
                    "DATE": "2026-02-30",
                }
            )
        )

        assert preview.records == ()
        assert preview.counts["failed"] == 1
        assert [error.code for error in preview.errors] == ["invalid_date"]

    def test_invalid_task_breaks_parent_chain_instead_of_reparenting_children(self):
        preview = parse_todoist_csv(
            make_csv(
                {"TYPE": "task", "CONTENT": "Original parent", "PRIORITY": "4", "INDENT": "1"},
                {"TYPE": "task", "CONTENT": "Invalid replacement", "PRIORITY": "9", "INDENT": "1"},
                {"TYPE": "task", "CONTENT": "Must not be reparented", "PRIORITY": "4", "INDENT": "2"},
            )
        )

        assert [record.content for record in preview.records] == ["Original parent"]
        assert [error.code for error in preview.errors] == ["invalid_priority", "invalid_hierarchy"]

    def test_duplicate_section_name_is_reported_and_resets_section_context(self):
        preview = parse_todoist_csv(
            make_csv(
                {"TYPE": "section", "CONTENT": "Planning"},
                {"TYPE": "section", "CONTENT": "planning"},
                {"TYPE": "task", "CONTENT": "After duplicate", "PRIORITY": "4", "INDENT": "1"},
            )
        )

        assert [error.code for error in preview.errors] == ["duplicate_section_name"]
        task = next(record for record in preview.records if record.kind == "task")
        assert task.section_row is None

    @pytest.mark.parametrize(
        ("content", "code"),
        [
            (b"", "empty_file"),
            (b"\xff", "invalid_encoding"),
            (b"TYPE,CONTENT\n\x00task,Example\n", "invalid_character"),
            (b"TYPE,CONTENT\ntask,Example\n", "missing_columns"),
            (b"TYPE,TYPE,CONTENT,DESCRIPTION,PRIORITY,INDENT\ntask,task,Example,,4,1\n", "duplicate_columns"),
            (b"x" * (MAX_FILE_BYTES + 1), "file_too_large"),
        ],
    )
    def test_rejects_invalid_files(self, content, code):
        with pytest.raises(TodoistImportParseError) as exc_info:
            parse_todoist_csv(content)

        assert exc_info.value.diagnostic.code == code

    def test_never_includes_cell_values_in_diagnostics(self):
        secret_value = "private-value-that-must-not-leak"
        preview = parse_todoist_csv(
            make_csv(
                {
                    "TYPE": "task",
                    "CONTENT": secret_value,
                    "PRIORITY": "invalid",
                    "INDENT": "1",
                }
            )
        )

        assert secret_value not in str([diagnostic.as_dict() for diagnostic in preview.diagnostics])
