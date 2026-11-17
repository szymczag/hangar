# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest


SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "upstream_watch"
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "upstream-watch.yml"
TESTS_WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "release-metadata-tests.yml"
SCRIPT_PATH = SCRIPTS_DIRECTORY / "upstream_watch.py"
sys.path.insert(0, str(SCRIPTS_DIRECTORY))
SPEC = importlib.util.spec_from_file_location("upstream_watch", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load upstream_watch.py")
upstream_watch = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = upstream_watch
SPEC.loader.exec_module(upstream_watch)

from release_metadata import UpstreamBase  # noqa: E402


RUN_URL = "https://github.com/szymczag/hangar/actions/runs/1"
# Recorded from the upstream API on 2026-11-17, trimmed to the fields read.
RELEASES = json.loads((FIXTURES / "releases.json").read_text(encoding="utf-8"))
ADVISORIES = json.loads((FIXTURES / "advisories.json").read_text(encoding="utf-8"))


def baseline(package_version="1.4.0", synced_at="2026-08-01"):
    return UpstreamBase(
        repository="https://github.com/makeplane/plane",
        revision="917b23a6c16d93fc00cef67900eff2755e8b13f7",
        package_version=package_version,
        synced_at=synced_at,
    )


def pending(package_version="1.4.0", synced_at="2026-08-01"):
    return (
        upstream_watch.pending_releases(RELEASES, package_version),
        upstream_watch.pending_advisories(
            ADVISORIES, synced_at, package_version, upstream_watch.latest_stable_version(RELEASES)
        ),
    )


def plan(open_issues, package_version="1.4.0", synced_at="2026-08-01"):
    releases, advisories = pending(package_version, synced_at)
    return upstream_watch.plan_issue(
        open_issues=open_issues,
        baseline=baseline(package_version, synced_at),
        releases=releases,
        advisories=advisories,
        run_url=RUN_URL,
    )


def issue_for(number, package_version="1.4.0", synced_at="2026-08-01"):
    releases, advisories = pending(package_version, synced_at)
    body = upstream_watch.render_issue_body(
        baseline=baseline(package_version, synced_at), releases=releases, advisories=advisories, run_url=RUN_URL
    )
    return {"number": number, "body": body}


class PendingReleasesTests(unittest.TestCase):
    def test_lists_stable_releases_newer_than_the_baseline_oldest_first(self):
        releases = upstream_watch.pending_releases(RELEASES, "1.4.0")
        self.assertEqual([release.tag for release in releases], ["v1.4.1", "v1.4.2", "v1.4.3", "v1.5.0"])
        self.assertEqual(releases[-1].url, "https://github.com/makeplane/plane/releases/tag/v1.5.0")

    def test_skips_prereleases_drafts_and_unparseable_tags(self):
        releases = [
            {"tag_name": "v1.6.0", "draft": True, "prerelease": False},
            {"tag_name": "v1.6.0-rc1", "draft": False, "prerelease": True},
            {"tag_name": "v1.6.0-rc2", "draft": False, "prerelease": False},
            {"tag_name": "nightly", "draft": False, "prerelease": False},
            {"tag_name": "v1.10.0", "draft": False, "prerelease": False},
        ]
        self.assertEqual([release.tag for release in upstream_watch.pending_releases(releases, "1.9.3")], ["v1.10.0"])

    def test_nothing_pending_at_the_latest_release(self):
        self.assertEqual(upstream_watch.pending_releases(RELEASES, "1.5.0"), [])

    def test_rejects_a_baseline_that_is_not_a_version(self):
        with self.assertRaises(upstream_watch.WatchError):
            upstream_watch.pending_releases(RELEASES, "preview")


class PendingAdvisoriesTests(unittest.TestCase):
    def test_lists_advisories_from_the_sync_day_on_oldest_first(self):
        advisories = upstream_watch.pending_advisories(ADVISORIES, "2026-08-01")
        self.assertEqual(
            [advisory.ghsa_id for advisory in advisories],
            ["GHSA-4vj8-p63v-8p24", "GHSA-wcc5-qgfr-8g9c", "GHSA-9382-fr89-xp7w"],
        )
        first = advisories[0]
        self.assertEqual((first.cve_id, first.severity, first.patched), ("CVE-2026-105639", "critical", "1.4.0"))
        self.assertEqual(advisories[-1].cve_id, "")

    def test_the_sync_day_itself_is_pending(self):
        self.assertEqual(
            [a.ghsa_id for a in upstream_watch.pending_advisories(ADVISORIES, "2026-11-16")], ["GHSA-9382-fr89-xp7w"]
        )
        self.assertEqual(upstream_watch.pending_advisories(ADVISORIES, "2026-11-17"), [])

    def test_an_advisory_fixed_after_the_baseline_stays_pending_past_its_date(self):
        """Hangar synced 1.4.3 on 2026-11-03; four advisories from 2026-09-28 are fixed only in 1.5.0."""
        fixed_later = dict(
            ADVISORIES[1],
            ghsa_id="GHSA-85h2-mhcc-xfmw",
            published_at="2026-09-28T07:00:01Z",
            vulnerabilities=[{"patched_versions": "1.5.0"}],
        )
        fixed_by_baseline = dict(ADVISORIES[1], vulnerabilities=[{"patched_versions": ">= 1.4.0"}])
        unversioned = dict(ADVISORIES[1], ghsa_id="GHSA-xxxx-xxxx-xxxx", vulnerabilities=[])
        advisories = [fixed_later, fixed_by_baseline, unversioned]
        self.assertEqual(
            [a.ghsa_id for a in upstream_watch.pending_advisories(advisories, "2026-11-03", "1.4.3", "1.5.0")],
            ["GHSA-85h2-mhcc-xfmw"],
        )
        # Without the versions only the date counts, as before.
        self.assertEqual(upstream_watch.pending_advisories(advisories, "2026-11-03"), [])
        self.assertEqual(upstream_watch.pending_advisories([fixed_later], "2026-11-03", "1.5.0", "1.5.0"), [])

    def test_a_patched_version_no_release_carries_does_not_keep_an_advisory_pending(self):
        """GHSA-6fj7-xgpg-mj6f (2025) names 1.18.0, which upstream has not released."""
        mistyped = dict(
            ADVISORIES[1],
            ghsa_id="GHSA-6fj7-xgpg-mj6f",
            published_at="2025-10-23T23:09:29Z",
            vulnerabilities=[{"patched_versions": "1.18.0"}],
        )
        self.assertEqual(upstream_watch.pending_advisories([mistyped], "2026-11-03", "1.4.3", "1.5.0"), [])

    def test_the_earliest_patched_release_decides(self):
        backported = dict(ADVISORIES[1], vulnerabilities=[{"patched_versions": "1.4.3, 1.5.0"}])
        self.assertEqual(upstream_watch.pending_advisories([backported], "2026-11-03", "1.4.3", "1.5.0"), [])
        self.assertEqual(len(upstream_watch.pending_advisories([backported], "2026-11-03", "1.4.2", "1.5.0")), 1)

    def test_rejects_versions_that_are_not_versions(self):
        with self.assertRaises(upstream_watch.WatchError):
            upstream_watch.pending_advisories(ADVISORIES, "2026-08-01", "preview", "1.5.0")
        with self.assertRaises(upstream_watch.WatchError):
            upstream_watch.pending_advisories(ADVISORIES, "2026-08-01", "1.4.3", "preview")

    def test_latest_stable_version_skips_prereleases(self):
        self.assertEqual(upstream_watch.latest_stable_version(RELEASES), "1.5.0")
        self.assertIsNone(upstream_watch.latest_stable_version([{"tag_name": "v9.0.0", "prerelease": True}]))

    def test_ignores_unpublished_advisories(self):
        withdrawn = dict(ADVISORIES[0], state="withdrawn")
        self.assertEqual(upstream_watch.pending_advisories([withdrawn], "2026-01-01"), [])


class PlanIssueTests(unittest.TestCase):
    def test_pending_changes_open_an_issue(self):
        actions = plan([])
        self.assertEqual([action.kind for action in actions], ["create"])
        body = actions[0].body
        self.assertIn("fingerprint=", body)
        self.assertIn("| [v1.5.0](https://github.com/makeplane/plane/releases/tag/v1.5.0) | 2026-11-16 |", body)
        self.assertIn("[GHSA-4vj8-p63v-8p24](", body)
        self.assertIn("CVE-2026-105639 | critical | 1.4.0 |", body)
        self.assertNotIn("GHSA-qw87-v5w3-6vxx", body)  # published before the sync

    def test_unchanged_pending_set_refreshes_quietly(self):
        self.assertEqual([action.kind for action in plan([issue_for(4)])], ["edit"])

    def test_changed_pending_set_comments_with_the_difference(self):
        # The issue was written against a later baseline, which listed only
        # 1.4.3, 1.5.0 and the advisories from September on.
        old = issue_for(4, package_version="1.4.2", synced_at="2026-09-01")
        actions = plan([old], package_version="1.4.0", synced_at="2026-08-01")
        self.assertEqual([action.kind for action in actions], ["edit", "comment"])
        comment = actions[1].body
        self.assertIn("New: GHSA-4vj8-p63v-8p24, v1.4.1, v1.4.2.", comment)
        self.assertNotIn("No longer pending", comment)

    def test_a_partial_sync_reports_what_is_no_longer_pending(self):
        actions = plan([issue_for(4)], package_version="1.4.3", synced_at="2026-10-28")
        self.assertEqual([action.kind for action in actions], ["edit", "comment"])
        self.assertIn(
            "No longer pending: GHSA-4vj8-p63v-8p24, GHSA-wcc5-qgfr-8g9c, v1.4.1, v1.4.2, v1.4.3.", actions[1].body
        )

    def test_a_full_sync_closes_the_issue(self):
        actions = plan([issue_for(4)], package_version="1.5.0", synced_at="2026-11-17")
        self.assertEqual([(action.kind, action.number) for action in actions], [("close", 4)])

    def test_nothing_pending_and_no_issue_does_nothing(self):
        self.assertEqual(plan([], package_version="1.5.0", synced_at="2026-11-17"), [])

    def test_keeps_exactly_one_issue_open(self):
        actions = plan([issue_for(9), issue_for(4), {"number": 2, "body": "unrelated, same label"}])
        self.assertEqual([(action.kind, action.number) for action in actions], [("edit", 4), ("close", 9)])
        self.assertIn("Duplicate of #4", actions[1].body)
        closed = plan([issue_for(9), issue_for(4)], package_version="1.5.0", synced_at="2026-11-17")
        self.assertEqual([(action.kind, action.number) for action in closed], [("close", 4), ("close", 9)])

    def test_fingerprint_ignores_order_and_cosmetic_fields(self):
        releases, advisories = pending()
        renamed = [upstream_watch.Advisory(a.ghsa_id, "", "low", "other", "", "", "") for a in advisories]
        self.assertEqual(
            upstream_watch.fingerprint(releases, advisories),
            upstream_watch.fingerprint(list(reversed(releases)), renamed),
        )

    def test_issue_body_round_trips_its_items(self):
        releases, advisories = pending()
        items = upstream_watch.read_items(issue_for(1)["body"])
        self.assertEqual(items, {r.tag for r in releases} | {a.ghsa_id for a in advisories})

    def test_table_cells_are_escaped(self):
        advisory = dict(ADVISORIES[0], summary="a | b\nc", published_at="2026-11-16T00:00:00Z")
        body = upstream_watch.render_issue_body(
            baseline=baseline(),
            releases=[],
            advisories=upstream_watch.pending_advisories([advisory], "2026-08-01"),
            run_url=RUN_URL,
        )
        self.assertIn("a \\| b c", body)


class CommandLineTests(unittest.TestCase):
    def run_main(self, *arguments):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = upstream_watch.main(list(arguments))
        return status, output.getvalue()

    def test_dry_run_reads_recorded_responses(self):
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary.md"
            status, output = self.run_main(
                "--baseline",
                str(REPOSITORY_ROOT / "UPSTREAM_BASE.json"),
                "--repository",
                "szymczag/hangar",
                "--run-url",
                RUN_URL,
                "--releases-json",
                str(FIXTURES / "releases.json"),
                "--advisories-json",
                str(FIXTURES / "advisories.json"),
                "--dry-run",
                "--step-summary",
                str(summary),
            )
            self.assertEqual(status, 0)
            self.assertIn("Pending upstream releases:", summary.read_text(encoding="utf-8"))
        self.assertIn("Tracking issue:", output)

    def test_invalid_baseline_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "UPSTREAM_BASE.json"
            path.write_text(json.dumps({"repository": "https://example.com/x"}), encoding="utf-8")
            status, output = self.run_main(
                "--baseline", str(path), "--repository", "szymczag/hangar", "--run-url", RUN_URL, "--dry-run"
            )
        self.assertEqual(status, 2)
        self.assertIn("::error::", output)


class UpstreamWatchWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_every_action_is_pinned_to_a_commit(self):
        uses = re.findall(r"uses: (\S+)", self.workflow)
        self.assertTrue(uses)
        for use in uses:
            with self.subTest(use=use):
                self.assertRegex(use, r"@[0-9a-f]{40}$")

    def test_runs_weekly_and_on_demand_with_narrow_permissions(self):
        self.assertRegex(self.workflow, r'schedule:\n    - cron: "\d+ \d+ \* \* \d"')
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("pull_request", self.workflow)
        permissions = self.workflow.split("\npermissions:\n", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
        self.assertEqual(sorted(permissions.split()), ["contents:", "issues:", "read", "write"])
        self.assertIn("timeout-minutes:", self.workflow)
        self.assertIn("\nconcurrency:\n", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)

    def test_creates_the_label_idempotently_and_runs_the_script(self):
        self.assertRegex(self.workflow, r"gh label create upstream-sync[^\n]*\n(?:\s+--[^\n]*\n)*\s+--force")
        self.assertIn("python3 .github/scripts/upstream_watch.py", self.workflow)
        self.assertIn("--baseline UPSTREAM_BASE.json", self.workflow)
        self.assertEqual(upstream_watch.ISSUE_LABEL, "upstream-sync")

    def test_the_unit_tests_run_when_the_watch_changes(self):
        tests_workflow = TESTS_WORKFLOW_PATH.read_text(encoding="utf-8")
        for path in (".github/scripts/upstream_watch.py", ".github/workflows/upstream-watch.yml", ".trivyignore.yaml"):
            with self.subTest(path=path):
                self.assertEqual(tests_workflow.count(f'- "{path}"'), 2)


if __name__ == "__main__":
    unittest.main()
