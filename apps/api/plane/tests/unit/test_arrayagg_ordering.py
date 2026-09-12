# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Every ArrayAgg must declare the order of the array it builds.

`array_agg(DISTINCT x)` returns its elements in an unspecified order. PostgreSQL
happens to dedupe by sorting, so today the arrays come back sorted by value and
nothing misbehaves -- but that is an implementation detail of the planner, not a
promise, and these arrays are serialised straight to the browser as `assignee_ids`,
`label_ids` and `module_ids`. A future plan shape that dedupes some other way
would reorder avatars and chips with no code change to blame.

The ordering is also free: the sort that `DISTINCT` already performs is the same
sort `ORDER BY` asks for, so naming it costs nothing and removes the assumption.

Use `order_by=`, not `ordering=`: Django 5.2 deprecated the latter and removes it
in 6.1, so the older spelling still works but warns on every query it builds.

This is a static check rather than a query, deliberately. A runtime assertion
would pass with or without the fix on PostgreSQL 15 and would prove nothing.
"""

import ast
import pathlib

import pytest

PLANE = pathlib.Path(__file__).resolve().parents[2]


def _arrayagg_calls():
    """Yield (path, lineno, has_ordering) for every ArrayAgg call under plane/."""
    for path in sorted(PLANE.rglob("*.py")):
        source = path.read_text()
        if "ArrayAgg(" not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name != "ArrayAgg":
                continue
            yield path.relative_to(PLANE), node.lineno, any(kw.arg == "order_by" for kw in node.keywords)


def test_the_scan_finds_the_call_sites_it_is_meant_to_guard():
    """A typo in the walk would make the guard below vacuously true."""
    assert sum(1 for _ in _arrayagg_calls()) > 40


def test_every_arrayagg_declares_an_ordering():
    unordered = [f"plane/{path}:{line}" for path, line, ordered in _arrayagg_calls() if not ordered]
    assert not unordered, "ArrayAgg without order_by=:\n  " + "\n  ".join(unordered)


@pytest.mark.parametrize("path,lineno,ordered", list(_arrayagg_calls()))
def test_ordering_matches_the_aggregated_expression(path, lineno, ordered):
    """PostgreSQL rejects `array_agg(DISTINCT x ORDER BY y)`: with DISTINCT the
    sort key has to be the aggregated expression itself, so the two must agree."""
    source = (PLANE / path).read_text()
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and node.lineno == lineno):
            continue
        func = node.func
        if (func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)) != "ArrayAgg":
            continue
        ordering = next(kw.value for kw in node.keywords if kw.arg == "order_by")
        assert ast.dump(ordering) == ast.dump(node.args[0]), f"plane/{path}:{lineno} orders by a different expression"
