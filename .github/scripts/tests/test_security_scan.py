# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest


SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "security-scan.yml"
SCRIPT_PATH = SCRIPTS_DIRECTORY / "security_scan.py"
sys.path.insert(0, str(SCRIPTS_DIRECTORY))
SPEC = importlib.util.spec_from_file_location("security_scan", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load security_scan.py")
security_scan = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = security_scan
SPEC.loader.exec_module(security_scan)

Finding = security_scan.Finding
ScanError = security_scan.ScanError

RUN_URL = "https://github.com/szymczag/hangar/actions/runs/1"
CODE_SCANNING_URL = "https://github.com/szymczag/hangar/security/code-scanning"

# Shape of `trivy image --format json` (0.76), trimmed to the fields read.
TRIVY_REPORT = {
    "SchemaVersion": 2,
    "ArtifactName": "ghcr.io/szymczag/hangar-web:v0.1.0-rc.70",
    "ArtifactType": "container_image",
    "Results": [
        {
            "Target": "ghcr.io/szymczag/hangar-web:v0.1.0-rc.70 (alpine 3.24.2)",
            "Class": "os-pkgs",
            "Type": "alpine",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2026-9947",
                    "PkgName": "libxslt",
                    "InstalledVersion": "1.1.43-r3",
                    "FixedVersion": "1.1.43-r4",
                    "Severity": "HIGH",
                    "Title": "chromium-browser: Use after free in XML",
                    "PrimaryURL": "https://avd.aquasec.com/nvd/cve-2026-9947",
                },
                {
                    "VulnerabilityID": "CVE-2026-87636",
                    "PkgName": "libxslt",
                    "InstalledVersion": "1.1.43-r3",
                    "FixedVersion": "1.1.43-r4",
                    "Severity": "HIGH",
                    "Title": "chromium-browser: Type confusion in XML",
                    "PrimaryURL": "https://avd.aquasec.com/nvd/cve-2026-87636",
                },
            ],
        },
        {"Target": "usr/local/lib/node_modules", "Class": "lang-pkgs", "Type": "node-pkg"},
    ],
}


def finding(image: str, vulnerability: str, package: str = "libxslt") -> Finding:
    return Finding(image, vulnerability, "HIGH", package, "1.0-r0", "1.0-r1", "", "")


def plan(existing, findings, errors=()):
    return security_scan.plan_report(
        existing=existing,
        tag="hangar-v0.1.0-rc.70",
        findings=findings,
        errors=list(errors),
        run_url=RUN_URL,
        code_scanning_url=CODE_SCANNING_URL,
    )


def issue_for(findings):
    body = security_scan.render_issue_body(
        tag="hangar-v0.1.0-rc.70",
        findings=findings,
        errors=[],
        run_url=RUN_URL,
        code_scanning_url=CODE_SCANNING_URL,
    )
    return {"number": 7, "body": body}


class SelectLatestReleaseTests(unittest.TestCase):
    def select(self, *tags, drafts=()):
        releases = [{"tagName": tag, "isDraft": False} for tag in tags]
        releases += [{"tagName": tag, "isDraft": True} for tag in drafts]
        return security_scan.select_latest_release(releases)

    def test_orders_release_candidates_numerically(self):
        self.assertEqual(
            self.select("hangar-v0.1.0-rc.9", "hangar-v0.1.0-rc.70", "hangar-v0.1.0-rc.69"),
            ("hangar-v0.1.0-rc.70", "v0.1.0-rc.70"),
        )

    def test_final_release_outranks_its_candidates(self):
        self.assertEqual(self.select("hangar-v0.1.0-rc.70", "hangar-v0.1.0")[0], "hangar-v0.1.0")
        self.assertEqual(self.select("hangar-v0.1.0", "hangar-v0.1.1-alpha.1")[0], "hangar-v0.1.1-alpha.1")
        self.assertEqual(self.select("hangar-v0.1.1-beta.2", "hangar-v0.1.1-alpha.9")[0], "hangar-v0.1.1-beta.2")

    def test_ignores_drafts_and_foreign_tags(self):
        # A draft has not finished publication; v* tags are upstream Plane's.
        self.assertEqual(
            self.select("hangar-v0.1.0-rc.70", "v1.3.1", "nightly", drafts=("hangar-v0.1.0-rc.71",))[0],
            "hangar-v0.1.0-rc.70",
        )

    def test_fails_without_a_release(self):
        with self.assertRaises(ScanError):
            self.select("v1.3.1", drafts=("hangar-v0.1.0-rc.71",))


class TrivyReportTests(unittest.TestCase):
    def test_parses_sorted_findings(self):
        findings = security_scan.parse_trivy_report(TRIVY_REPORT, "web")
        self.assertEqual([f.vulnerability for f in findings], ["CVE-2026-87636", "CVE-2026-9947"])
        self.assertEqual(findings[0].fixed, "1.1.43-r4")
        self.assertEqual(findings[0].url, "https://avd.aquasec.com/nvd/cve-2026-87636")

    def test_clean_report_has_no_findings(self):
        clean = {"ArtifactName": "x", "Results": [{"Target": "x", "Class": "os-pkgs"}]}
        self.assertEqual(security_scan.parse_trivy_report(clean, "web"), [])
        self.assertEqual(security_scan.parse_trivy_report({"ArtifactName": "x"}, "web"), [])

    def test_rejects_something_else(self):
        with self.assertRaises(ScanError):
            security_scan.parse_trivy_report({"runs": []}, "web")

    def test_table_escapes_cells(self):
        table = security_scan.render_table([Finding("web", "CVE-1", "HIGH", "a|b", "1", "2", "", "")])
        self.assertIn("a\\|b", table)

    def test_summarize_writes_findings_and_fails_on_request(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "trivy.json"
            report.write_text(json.dumps(TRIVY_REPORT), encoding="utf-8")
            output = Path(directory) / "out" / "findings-web.json"
            summary = Path(directory) / "summary.md"
            arguments = [
                "summarize",
                "--image",
                "web",
                "--image-ref",
                "ghcr.io/szymczag/hangar-web:v0.1.0-rc.70",
                "--report",
                str(report),
                "--output",
                str(output),
                "--step-summary",
                str(summary),
            ]
            self.assertEqual(security_scan.main(arguments), 0)
            self.assertEqual(security_scan.main([*arguments, "--fail-on-findings"]), 1)
            written = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(written["image"], "web")
            self.assertEqual(len(written["findings"]), 2)
            self.assertIn("2 finding(s)", summary.read_text(encoding="utf-8"))


class CollectResultsTests(unittest.TestCase):
    def test_missing_file_means_not_scanned(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "findings-web.json"
            path.write_text(
                json.dumps({"image": "web", "findings": [finding("web", "CVE-1").to_dict()]}),
                encoding="utf-8",
            )
            (Path(directory) / "findings-api.json").write_text(
                json.dumps({"image": "api", "findings": []}), encoding="utf-8"
            )
            findings, errors = security_scan.collect_results(Path(directory), ["web", "api", "proxy"])
        self.assertEqual([f.vulnerability for f in findings], ["CVE-1"])
        self.assertEqual(errors, ["proxy"])

    def test_rejects_a_file_for_another_image(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "findings-web.json").write_text(
                json.dumps({"image": "api", "findings": []}), encoding="utf-8"
            )
            with self.assertRaises(ScanError):
                security_scan.collect_results(Path(directory), ["web"])


class PlanReportTests(unittest.TestCase):
    def test_fingerprint_ignores_order_and_cosmetic_fields(self):
        a = [finding("web", "CVE-1"), finding("api", "CVE-2")]
        b = [Finding("api", "CVE-2", "CRITICAL", "libxslt", "x", "y", "t", "u"), finding("web", "CVE-1")]
        self.assertEqual(security_scan.fingerprint(a), security_scan.fingerprint(b))
        self.assertNotEqual(security_scan.fingerprint(a), security_scan.fingerprint(a[:1]))

    def test_findings_open_an_issue(self):
        actions = plan(None, [finding("web", "CVE-1")])
        self.assertEqual([a.kind for a in actions], ["create"])
        self.assertIn("hangar-v0.1.0-rc.70", actions[0].body)
        self.assertEqual(security_scan.read_fingerprint(actions[0].body), security_scan.fingerprint([finding("web", "CVE-1")]))

    def test_unchanged_findings_refresh_quietly(self):
        findings = [finding("web", "CVE-1")]
        actions = plan(issue_for(findings), findings)
        self.assertEqual([(a.kind, a.number) for a in actions], [("edit", 7)])

    def test_changed_findings_comment(self):
        existing = issue_for([finding("web", "CVE-1"), finding("api", "CVE-2")])
        actions = plan(existing, [finding("web", "CVE-1"), finding("web", "CVE-3")])
        self.assertEqual([a.kind for a in actions], ["edit", "comment"])
        self.assertIn("New: `web` CVE-3.", actions[1].body)
        self.assertIn("No longer found: `api` CVE-2.", actions[1].body)

    def test_clean_scan_closes_the_issue(self):
        actions = plan(issue_for([finding("web", "CVE-1")]), [])
        self.assertEqual([(a.kind, a.number) for a in actions], [("close", 7)])
        self.assertEqual(plan(None, []), [])

    def test_an_unscanned_image_never_closes_or_resolves(self):
        existing = issue_for([finding("web", "CVE-1")])
        self.assertEqual(plan(existing, [], errors=["web"]), [])
        self.assertEqual(plan(existing, [finding("api", "CVE-2")], errors=["web"]), [])

    def test_an_unscanned_image_still_lets_new_findings_open_an_issue(self):
        actions = plan(None, [finding("api", "CVE-2")], errors=["web"])
        self.assertEqual([a.kind for a in actions], ["create"])
        self.assertIn("Not scanned in the latest run: `web`.", actions[0].body)

    def test_parse_issue_findings_round_trips(self):
        findings = [finding("web", "CVE-1"), Finding("api", "CVE-2", "HIGH", "p", "1", "2", "t", "https://x")]
        parsed = security_scan.parse_issue_findings(issue_for(findings)["body"])
        self.assertEqual({(f.image, f.vulnerability) for f in parsed}, {("web", "CVE-1"), ("api", "CVE-2")})


class SecurityScanWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.jobs = {}
        body = cls.workflow.split("\njobs:\n", maxsplit=1)[1]
        for match in re.finditer(r"^  ([a-z_]+):\n(.*?)(?=^  [a-z_]+:\n|\Z)", body, re.S | re.M):
            cls.jobs[match[1]] = match[2]

    def test_every_action_is_pinned_to_a_commit(self):
        for use in re.findall(r"uses: (\S+)", self.workflow):
            with self.subTest(use=use):
                self.assertRegex(use, r"@[0-9a-f]{40}$")

    def test_trivy_signature_is_verified_once_with_retries(self):
        self.assertEqual(set(self.jobs), {"python", "node", "trivy", "repository", "release", "images", "report"})
        for name, job in self.jobs.items():
            with self.subTest(job=name):
                if name == "trivy":
                    self.assertEqual(job.count("uses: sigstore/cosign-installer@"), 2)
                    self.assertIn("continue-on-error: true", job)
                    self.assertIn("cosign verify", job)
                else:
                    self.assertNotIn("cosign", job)
        for name in ("repository", "images"):
            with self.subTest(job=name):
                self.assertIn("trivy", re.search(r"needs: (.*)", self.jobs[name])[1])

    def test_images_come_from_the_published_release(self):
        self.assertIn("security_scan.py resolve", self.jobs["release"])
        self.assertIn("--exclude-drafts", self.jobs["release"])
        self.assertIn("needs: [trivy, release]", self.jobs["images"])
        self.assertIn("needs.release.outputs.version", self.jobs["images"])
        self.assertNotIn("git tag", self.workflow)
        self.assertIn("docker buildx imagetools inspect", self.jobs["images"])

    def test_release_publication_triggers_a_scan(self):
        self.assertIn('workflows: ["Publish Hangar Containers"]', self.workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", self.jobs["release"])
        self.assertIn("github.event.workflow_run.event == 'push'", self.jobs["release"])
        for name in ("python", "node", "repository"):
            with self.subTest(job=name):
                self.assertIn("if: github.event_name != 'workflow_run'", self.jobs[name])

    def test_image_matrix_matches_the_report(self):
        matrix = re.search(r"image: \[(.*)\]", self.jobs["images"])[1].replace(" ", "").split(",")
        self.assertEqual(tuple(matrix), security_scan.IMAGE_NAMES)
        self.assertIn("--images " + ",".join(matrix), self.jobs["report"])

    def test_only_the_report_writes_issues(self):
        for name, job in self.jobs.items():
            with self.subTest(job=name):
                if name == "report":
                    self.assertIn("issues: write", job)
                else:
                    self.assertNotIn("issues:", job)
        self.assertIn("if: always() && needs.release.result == 'success'", self.jobs["report"])


if __name__ == "__main__":
    unittest.main()
