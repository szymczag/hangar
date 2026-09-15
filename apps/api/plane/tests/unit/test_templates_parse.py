# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Every template in the tree must compile.

A template that cannot be parsed is invisible to a container health check: the
process starts, the probe passes, and the feature that renders it is dead. That
is exactly how issue-updates.html stopped every activity notification -- a
formatter reflowed three `{% if %}` tags across newlines, and Django's lexer
(`tag_re`, compiled without `re.DOTALL`) stopped recognising them as tags at all.
The task raised on every run for days while everything else looked healthy.

Parsing the whole tree costs milliseconds and catches that class at commit time.
"""

from pathlib import Path

import pytest
from django.template import TemplateSyntaxError
from django.template.loader import get_template

TEMPLATE_ROOT = Path(__file__).resolve().parents[3] / "templates"


def _template_names():
    return sorted(str(path.relative_to(TEMPLATE_ROOT)) for path in TEMPLATE_ROOT.rglob("*.html"))


@pytest.mark.unit
class TestTemplatesParse:
    def test_the_template_directory_is_where_we_think_it_is(self):
        """A wrong root would make every test below pass by finding nothing."""
        assert TEMPLATE_ROOT.is_dir(), f"No template directory at {TEMPLATE_ROOT}"
        assert len(_template_names()) > 0

    @pytest.mark.parametrize("name", _template_names())
    def test_template_compiles(self, name):
        try:
            get_template(name)
        except TemplateSyntaxError as error:
            pytest.fail(
                f"{name} does not compile: {error}\n"
                "A tag split across lines is the usual cause -- Django's lexer does not "
                "match a newline inside {% %}, so the opener is never tokenised and its "
                "closer pairs with whatever block encloses it. The reported line is where "
                "the parser noticed, not where the break is."
            )


@pytest.mark.unit
class TestTemplateTagsAreSingleLine:
    """The shape that breaks parsing, caught directly rather than by its symptom.

    A split tag does not always fail to parse. One whose opener happens to
    balance still silently loses its condition, and a string literal broken
    across lines can never match the value it is compared against. Neither
    raises, so the parse test above would pass while the feature stayed wrong.
    """

    @pytest.mark.parametrize("name", _template_names())
    def test_no_tag_spans_a_newline(self, name):
        offenders = []
        for number, line in enumerate((TEMPLATE_ROOT / name).read_text().splitlines(), start=1):
            for opener, closer in (("{%", "%}"), ("{{", "}}")):
                if line.count(opener) != line.count(closer):
                    offenders.append(f"  line {number}: {line.strip()[:100]}")
                    break
        assert not offenders, f"{name} has template tags spanning a newline:\n" + "\n".join(offenders)
