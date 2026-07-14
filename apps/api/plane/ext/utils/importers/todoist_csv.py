# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from io import StringIO
from typing import Literal


MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10_000
MAX_COLUMNS = 32
MAX_CELL_CHARACTERS = 65_536
MAX_TITLE_CHARACTERS = 255

REQUIRED_COLUMNS = frozenset({"type", "content", "description", "priority", "indent"})
SUPPORTED_ROW_TYPES = frozenset({"meta", "project_note", "section", "task", "note"})
PRIORITY_MAP = {"1": "urgent", "2": "high", "3": "medium", "4": "none"}
ISO_DATE_PREFIX = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})(?:[ T].*)?$")

RecordKind = Literal["project_note", "section", "task", "note"]
DiagnosticLevel = Literal["error", "warning"]


@dataclass(frozen=True, slots=True)
class ImportDiagnostic:
    level: DiagnosticLevel
    code: str
    message: str
    row: int | None = None
    field: str | None = None

    def as_dict(self) -> dict[str, str | int | None]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "row": self.row,
            "field": self.field,
        }


@dataclass(frozen=True, slots=True)
class TodoistRecord:
    kind: RecordKind
    row: int
    content: str
    description: str = ""
    priority: str = "none"
    indent: int | None = None
    parent_row: int | None = None
    section_row: int | None = None
    task_row: int | None = None
    author: str = ""
    responsible: str = ""
    scheduled_date: date | None = None
    deadline: date | None = None
    unsupported_schedule: str = ""
    timezone: str = ""
    duration: str = ""
    duration_unit: str = ""


@dataclass(frozen=True, slots=True)
class TodoistImportPreview:
    digest: str
    headers: tuple[str, ...]
    records: tuple[TodoistRecord, ...]
    diagnostics: tuple[ImportDiagnostic, ...]
    counts: dict[str, int] = field(default_factory=dict)
    assignees: tuple[str, ...] = ()

    @property
    def errors(self) -> tuple[ImportDiagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.level == "error")

    @property
    def warnings(self) -> tuple[ImportDiagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.level == "warning")


class TodoistImportParseError(ValueError):
    def __init__(self, diagnostic: ImportDiagnostic):
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


@dataclass(slots=True)
class _ParserState:
    current_section_row: int | None = None
    current_task_row: int | None = None
    parent_stack: dict[int, int] = field(default_factory=dict)

    def reset_task_chain(self, from_indent: int | None = None) -> None:
        self.current_task_row = None
        if from_indent is None:
            self.parent_stack.clear()
            return
        for level in range(from_indent, 5):
            self.parent_stack.pop(level, None)

    def reset_section(self) -> None:
        self.current_section_row = None
        self.reset_task_chain()

    def start_section(self, row: int) -> None:
        self.current_section_row = row
        self.reset_task_chain()


def _fatal(code: str, message: str, *, row: int | None = None, field: str | None = None) -> None:
    raise TodoistImportParseError(ImportDiagnostic(level="error", code=code, message=message, row=row, field=field))


def _parse_date(
    value: str,
    *,
    row: int,
    field_name: str,
    diagnostics: list[ImportDiagnostic],
) -> tuple[date | None, str]:
    normalized = value.strip()
    if not normalized:
        return None, ""

    match = ISO_DATE_PREFIX.fullmatch(normalized)
    if match:
        try:
            parsed_date = date.fromisoformat(match.group("date"))
            if normalized != match.group("date"):
                diagnostics.append(
                    ImportDiagnostic(
                        level="warning",
                        code="schedule_time_not_preserved",
                        message="The date will be imported, while its time will be preserved as import metadata.",
                        row=row,
                        field=field_name,
                    )
                )
                return parsed_date, normalized
            return parsed_date, ""
        except ValueError:
            diagnostics.append(
                ImportDiagnostic(
                    level="error",
                    code="invalid_date",
                    message="The date is not a valid calendar date.",
                    row=row,
                    field=field_name,
                )
            )
            return None, ""

    diagnostics.append(
        ImportDiagnostic(
            level="warning",
            code="unsupported_schedule",
            message="The schedule cannot be converted to a Hangar date and will be preserved as import metadata.",
            row=row,
            field=field_name,
        )
    )
    return None, normalized


def _normalize_row(row: dict[str | None, str | list[str] | None]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in row.items():
        if key is None:
            continue
        normalized[key.strip().lower()] = value if isinstance(value, str) else ""
    return normalized


def parse_todoist_csv(content: bytes) -> TodoistImportPreview:
    """Parse and structurally validate a Todoist project CSV export."""

    if not content:
        _fatal("empty_file", "The CSV file is empty.")
    if len(content) > MAX_FILE_BYTES:
        _fatal("file_too_large", "The CSV file exceeds the 5 MiB import limit.")
    if b"\x00" in content:
        _fatal("invalid_character", "The CSV file contains a NUL byte.")

    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        _fatal("invalid_encoding", "The CSV file must use UTF-8 encoding.")

    previous_field_limit = csv.field_size_limit()
    csv.field_size_limit(MAX_CELL_CHARACTERS)
    try:
        reader = csv.DictReader(StringIO(decoded, newline=""))
        original_headers = tuple(reader.fieldnames or ())
        if not original_headers:
            _fatal("missing_header", "The CSV file does not contain a header row.")
        if len(original_headers) > MAX_COLUMNS:
            _fatal("too_many_columns", "The CSV file contains too many columns.")

        normalized_headers = tuple(header.strip().lower() for header in original_headers)
        if len(set(normalized_headers)) != len(normalized_headers):
            _fatal("duplicate_columns", "The CSV header contains duplicate columns.")

        missing_columns = sorted(REQUIRED_COLUMNS.difference(normalized_headers))
        if missing_columns:
            _fatal(
                "missing_columns",
                "The CSV file is missing one or more required Todoist columns.",
                field=missing_columns[0],
            )

        records: list[TodoistRecord] = []
        diagnostics: list[ImportDiagnostic] = []
        counts: Counter[str] = Counter()
        assignees: set[str] = set()
        state = _ParserState()
        section_names: set[str] = set()
        row_count = 0

        try:
            for index, source_row in enumerate(reader, start=2):
                row_count += 1
                if row_count > MAX_ROWS:
                    _fatal("too_many_rows", "The CSV file exceeds the 10,000-row import limit.")
                if None in source_row:
                    diagnostics.append(
                        ImportDiagnostic(
                            level="error",
                            code="column_mismatch",
                            message="The row contains more values than the CSV header.",
                            row=index,
                        )
                    )
                    counts["failed"] += 1
                    state.reset_task_chain()
                    continue

                row = _normalize_row(source_row)
                if any(len(value) > MAX_CELL_CHARACTERS for value in row.values()):
                    diagnostics.append(
                        ImportDiagnostic(
                            level="error",
                            code="cell_too_large",
                            message="A cell exceeds the 65,536-character import limit.",
                            row=index,
                        )
                    )
                    counts["failed"] += 1
                    state.reset_task_chain()
                    continue

                if not any(value.strip() for value in row.values()):
                    counts["blank"] += 1
                    state.reset_task_chain()
                    continue

                row_type = row.get("type", "").strip().lower()
                if row_type not in SUPPORTED_ROW_TYPES:
                    diagnostics.append(
                        ImportDiagnostic(
                            level="error",
                            code="unsupported_row_type",
                            message="The row type is not supported by the Todoist importer.",
                            row=index,
                            field="type",
                        )
                    )
                    counts["failed"] += 1
                    state.reset_task_chain()
                    continue

                content_value = row.get("content", "").strip()
                if row_type == "meta":
                    counts["meta"] += 1
                    state.reset_task_chain()
                    continue

                if not content_value:
                    diagnostics.append(
                        ImportDiagnostic(
                            level="error",
                            code="missing_content",
                            message="The row requires non-empty content.",
                            row=index,
                            field="content",
                        )
                    )
                    counts["failed"] += 1
                    if row_type == "section":
                        state.reset_section()
                    elif row_type == "task":
                        state.reset_task_chain()
                    else:
                        state.current_task_row = None
                    continue

                if row_type == "project_note":
                    records.append(TodoistRecord(kind="project_note", row=index, content=content_value))
                    counts["project_note"] += 1
                    state.reset_task_chain()
                    continue

                if row_type == "section":
                    if len(content_value) > MAX_TITLE_CHARACTERS:
                        diagnostics.append(
                            ImportDiagnostic(
                                level="error",
                                code="section_name_too_long",
                                message="The section name exceeds Hangar's 255-character limit.",
                                row=index,
                                field="content",
                            )
                        )
                        counts["failed"] += 1
                        state.reset_section()
                        continue
                    normalized_section_name = content_value.casefold()
                    if normalized_section_name in section_names:
                        diagnostics.append(
                            ImportDiagnostic(
                                level="error",
                                code="duplicate_section_name",
                                message="Section names must be unique within one import file.",
                                row=index,
                                field="content",
                            )
                        )
                        counts["failed"] += 1
                        state.reset_section()
                        continue
                    section_names.add(normalized_section_name)
                    records.append(TodoistRecord(kind="section", row=index, content=content_value))
                    counts["section"] += 1
                    state.start_section(index)
                    continue

                if row_type == "note":
                    if state.current_task_row is None:
                        diagnostics.append(
                            ImportDiagnostic(
                                level="error",
                                code="orphan_note",
                                message="The note does not follow a task that it can be attached to.",
                                row=index,
                                field="type",
                            )
                        )
                        counts["failed"] += 1
                        continue
                    records.append(
                        TodoistRecord(
                            kind="note",
                            row=index,
                            content=content_value,
                            task_row=state.current_task_row,
                            author=row.get("author", "").strip(),
                        )
                    )
                    counts["note"] += 1
                    continue

                if len(content_value) > MAX_TITLE_CHARACTERS:
                    diagnostics.append(
                        ImportDiagnostic(
                            level="error",
                            code="title_too_long",
                            message="The task title exceeds Hangar's 255-character limit.",
                            row=index,
                            field="content",
                        )
                    )
                    counts["failed"] += 1
                    state.reset_task_chain()
                    continue

                priority_value = row.get("priority", "").strip() or "4"
                if priority_value not in PRIORITY_MAP:
                    diagnostics.append(
                        ImportDiagnostic(
                            level="error",
                            code="invalid_priority",
                            message="The task priority must be a number from 1 through 4.",
                            row=index,
                            field="priority",
                        )
                    )
                    counts["failed"] += 1
                    state.reset_task_chain()
                    continue

                indent_value = row.get("indent", "").strip() or "1"
                try:
                    indent = int(indent_value)
                except ValueError:
                    indent = 0
                if indent not in {1, 2, 3, 4}:
                    diagnostics.append(
                        ImportDiagnostic(
                            level="error",
                            code="invalid_indent",
                            message="The task indent must be a number from 1 through 4.",
                            row=index,
                            field="indent",
                        )
                    )
                    counts["failed"] += 1
                    state.reset_task_chain()
                    continue

                parent_row = state.parent_stack.get(indent - 1) if indent > 1 else None
                if indent > 1 and parent_row is None:
                    diagnostics.append(
                        ImportDiagnostic(
                            level="error",
                            code="invalid_hierarchy",
                            message="The task hierarchy skips a required parent level.",
                            row=index,
                            field="indent",
                        )
                    )
                    counts["failed"] += 1
                    state.reset_task_chain(indent)
                    continue

                diagnostic_count = len(diagnostics)
                scheduled_date, unsupported_date = _parse_date(
                    row.get("date", ""), row=index, field_name="date", diagnostics=diagnostics
                )
                deadline, unsupported_deadline = _parse_date(
                    row.get("deadline", ""), row=index, field_name="deadline", diagnostics=diagnostics
                )
                if any(item.level == "error" for item in diagnostics[diagnostic_count:]):
                    counts["failed"] += 1
                    state.reset_task_chain(indent)
                    continue
                responsible = row.get("responsible", "").strip()
                if responsible:
                    assignees.add(responsible)

                records.append(
                    TodoistRecord(
                        kind="task",
                        row=index,
                        content=content_value,
                        description=row.get("description", "").strip(),
                        priority=PRIORITY_MAP[priority_value],
                        indent=indent,
                        parent_row=parent_row,
                        section_row=state.current_section_row,
                        author=row.get("author", "").strip(),
                        responsible=responsible,
                        scheduled_date=scheduled_date,
                        deadline=deadline,
                        unsupported_schedule="; ".join(
                            value for value in (unsupported_date, unsupported_deadline) if value
                        ),
                        timezone=row.get("timezone", "").strip(),
                        duration=row.get("duration", "").strip(),
                        duration_unit=row.get("duration_unit", "").strip(),
                    )
                )
                counts["task"] += 1
                state.current_task_row = index
                state.parent_stack[indent] = index
                for level in range(indent + 1, 5):
                    state.parent_stack.pop(level, None)
        except csv.Error:
            _fatal("malformed_csv", "The CSV file is malformed and cannot be parsed.")

        counts["rows"] = row_count
        counts.setdefault("failed", 0)
        counts["importable"] = len(records)
        return TodoistImportPreview(
            digest=hashlib.sha256(content).hexdigest(),
            headers=normalized_headers,
            records=tuple(records),
            diagnostics=tuple(diagnostics),
            counts=dict(counts),
            assignees=tuple(sorted(assignees, key=str.casefold)),
        )
    finally:
        csv.field_size_limit(previous_field_limit)
