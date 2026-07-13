# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import importlib.util
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "release_metadata.py"
SPEC = importlib.util.spec_from_file_location("release_metadata", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load release_metadata.py")
release_metadata = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release_metadata
SPEC.loader.exec_module(release_metadata)

MetadataError = release_metadata.MetadataError
UpstreamBase = release_metadata.UpstreamBase


VALID_COMMIT = "a" * 40
VALID_UPSTREAM = UpstreamBase(
    repository="https://github.com/makeplane/plane",
    revision="b" * 40,
    package_version="1.3.1",
    synced_at="2026-07-09",
)


class ReleaseTagTests(unittest.TestCase):
    def test_stable_tag(self):
        metadata = release_metadata.build_release_metadata(
            event_name="push",
            ref_name="hangar-v1.2.3",
            commit_sha=VALID_COMMIT,
            upstream=VALID_UPSTREAM,
        )

        self.assertEqual(metadata.git_tag, "hangar-v1.2.3")
        self.assertEqual(metadata.version, "v1.2.3")
        self.assertEqual(metadata.primary_tag, "v1.2.3")
        self.assertEqual(metadata.release_title, "Hangar v1.2.3")
        self.assertEqual(metadata.sha_tag, f"sha-{VALID_COMMIT}")
        self.assertTrue(metadata.is_release)
        self.assertFalse(metadata.is_prerelease)

    def test_approved_prerelease_tags(self):
        for stage in ("alpha", "beta", "rc"):
            with self.subTest(stage=stage):
                version, is_prerelease = release_metadata.parse_release_tag(
                    f"hangar-v0.1.0-{stage}.12"
                )
                self.assertEqual(version, f"v0.1.0-{stage}.12")
                self.assertTrue(is_prerelease)

    def test_rejects_unsafe_or_unsupported_tags(self):
        invalid_tags = (
            "v1.3.1",
            "hangar-v01.2.3",
            "hangar-v1.02.3",
            "hangar-v1.2.03",
            "hangar-v1.2.3-rc.0",
            "hangar-v1.2.3-rc.01",
            "hangar-v1.2.3-dev.1",
            "hangar-v1.2.3-hangar.1",
            "hangar-v1.2.3+build.1",
            "hangar-v1.2.3\nforged=true",
            "hangar-v1.2",
            "",
        )

        for tag in invalid_tags:
            with self.subTest(tag=tag), self.assertRaises(MetadataError):
                release_metadata.parse_release_tag(tag)

    def test_rejects_invalid_commit_sha(self):
        for commit in ("ABCDEF" * 6 + "ABCD", "a" * 39, "a" * 41, "g" * 40, "a" * 39 + "\n"):
            with self.subTest(commit=commit), self.assertRaises(MetadataError):
                release_metadata.build_release_metadata(
                    event_name="push",
                    ref_name="hangar-v1.2.3",
                    commit_sha=commit,
                    upstream=VALID_UPSTREAM,
                )


class PreviewMetadataTests(unittest.TestCase):
    def test_normalizes_preview_ref(self):
        metadata = release_metadata.build_release_metadata(
            event_name="workflow_dispatch",
            ref_name="Feature/Release Safety",
            commit_sha=VALID_COMMIT,
            upstream=VALID_UPSTREAM,
        )

        self.assertEqual(metadata.primary_tag, "preview-feature-release-safety")
        self.assertEqual(metadata.version, "feature-release-safety")
        self.assertEqual(metadata.sha_tag, f"preview-sha-{VALID_COMMIT}")
        self.assertIsNone(metadata.git_tag)
        self.assertFalse(metadata.is_release)
        self.assertFalse(metadata.is_prerelease)

    def test_long_preview_refs_are_bounded_and_collision_resistant(self):
        first = release_metadata.normalize_preview_ref("feature/" + "a" * 200 + "-one")
        second = release_metadata.normalize_preview_ref("feature/" + "a" * 200 + "-two")

        self.assertLessEqual(len(first), release_metadata.MAX_OCI_TAG_LENGTH)
        self.assertLessEqual(len(second), release_metadata.MAX_OCI_TAG_LENGTH)
        self.assertNotEqual(first, second)

    def test_rejects_empty_or_control_only_preview_refs(self):
        for ref_name in ("", "...", "---", "\n", "feature\x7fref"):
            with self.subTest(ref_name=ref_name), self.assertRaises(MetadataError):
                release_metadata.normalize_preview_ref(ref_name)


class UpstreamBaseTests(unittest.TestCase):
    def write_baseline(self, directory: Path, data):
        path = directory / "UPSTREAM_BASE.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def valid_baseline(self):
        return {
            "repository": "https://github.com/makeplane/plane",
            "revision": "b" * 40,
            "package_version": "1.3.1",
            "synced_at": "2026-07-09",
        }

    def test_loads_valid_baseline(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = self.write_baseline(Path(temporary_directory), self.valid_baseline())
            baseline = release_metadata.load_upstream_base(path)

        self.assertEqual(baseline, VALID_UPSTREAM)

    def test_rejects_schema_changes(self):
        cases = []
        missing = self.valid_baseline()
        del missing["synced_at"]
        cases.append(missing)
        unexpected = self.valid_baseline()
        unexpected["url"] = unexpected["repository"]
        cases.append(unexpected)
        wrong_type = self.valid_baseline()
        wrong_type["package_version"] = 131
        cases.append(wrong_type)

        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            for index, data in enumerate(cases):
                with self.subTest(index=index), self.assertRaises(MetadataError):
                    release_metadata.load_upstream_base(self.write_baseline(directory, data))

    def test_rejects_unapproved_repository(self):
        data = self.valid_baseline()
        data["repository"] = "https://github.com/example/plane"

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = self.write_baseline(Path(temporary_directory), data)
            with self.assertRaisesRegex(MetadataError, "approved Plane repository"):
                release_metadata.load_upstream_base(path)

    def test_rejects_invalid_revision_package_version_and_date(self):
        cases = (
            ("revision", "B" * 40),
            ("revision", "b" * 39),
            ("package_version", "1.3.1\nforged"),
            ("synced_at", "2026-7-9"),
            ("synced_at", "2026-02-30"),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            for field, value in cases:
                data = self.valid_baseline()
                data[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(MetadataError):
                    release_metadata.load_upstream_base(self.write_baseline(directory, data))


class GitAncestryTests(unittest.TestCase):
    def git(self, repository: Path, *arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def create_repository(self, directory: Path) -> tuple[str, str]:
        self.git(directory, "init", "--initial-branch=main")
        self.git(directory, "config", "user.name", "Release Metadata Tests")
        self.git(directory, "config", "user.email", "tests@example.invalid")
        self.git(directory, "config", "commit.gpgsign", "false")
        self.git(directory, "commit", "--allow-empty", "-m", "upstream baseline")
        upstream_revision = self.git(directory, "rev-parse", "HEAD")
        self.git(directory, "commit", "--allow-empty", "-m", "hangar change")
        release_commit = self.git(directory, "rev-parse", "HEAD")
        return upstream_revision, release_commit

    def test_accepts_ancestor(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            upstream_revision, release_commit = self.create_repository(repository)

            release_metadata.validate_upstream_ancestry(
                repository_root=repository,
                upstream_revision=upstream_revision,
                release_commit=release_commit,
            )

    def test_rejects_missing_revision(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            _, release_commit = self.create_repository(repository)

            with self.assertRaisesRegex(MetadataError, "upstream revision does not exist"):
                release_metadata.validate_upstream_ancestry(
                    repository_root=repository,
                    upstream_revision="f" * 40,
                    release_commit=release_commit,
                )

    def test_rejects_non_ancestor(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            baseline, release_commit = self.create_repository(repository)
            self.git(repository, "switch", "--detach", baseline)
            self.git(repository, "commit", "--allow-empty", "-m", "unmerged upstream")
            unmerged_upstream = self.git(repository, "rev-parse", "HEAD")

            with self.assertRaisesRegex(MetadataError, "not an ancestor"):
                release_metadata.validate_upstream_ancestry(
                    repository_root=repository,
                    upstream_revision=unmerged_upstream,
                    release_commit=release_commit,
                )


class CommandLineTests(unittest.TestCase):
    def git(self, repository: Path, *arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def test_cli_outputs_deterministic_json_without_repository_changes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            self.git(repository, "init", "--initial-branch=main")
            self.git(repository, "config", "user.name", "Release Metadata Tests")
            self.git(repository, "config", "user.email", "tests@example.invalid")
            self.git(repository, "config", "commit.gpgsign", "false")
            self.git(repository, "commit", "--allow-empty", "-m", "upstream baseline")
            upstream_revision = self.git(repository, "rev-parse", "HEAD")
            self.git(repository, "commit", "--allow-empty", "-m", "hangar release")
            release_commit = self.git(repository, "rev-parse", "HEAD")
            (repository / "UPSTREAM_BASE.json").write_text(
                json.dumps(
                    {
                        "repository": "https://github.com/makeplane/plane",
                        "revision": upstream_revision,
                        "package_version": "1.3.1",
                        "synced_at": "2026-07-09",
                    }
                ),
                encoding="utf-8",
            )
            before = self.git(repository, "status", "--porcelain")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--event-name",
                    "push",
                    "--ref-name",
                    "hangar-v0.1.0-rc.1",
                    "--commit-sha",
                    release_commit,
                    "--repository-root",
                    str(repository),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            after = self.git(repository, "status", "--porcelain")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(before, after)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["git_tag"], "hangar-v0.1.0-rc.1")
        self.assertEqual(payload["version"], "v0.1.0-rc.1")
        self.assertEqual(payload["upstream"]["revision"], upstream_revision)

    def test_cli_rejects_unnamespaced_release_tag(self):
        repository_root = SCRIPT_PATH.parents[2]
        release_commit = self.git(repository_root, "rev-parse", "HEAD")
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--event-name",
                "push",
                "--ref-name",
                "v1.3.1",
                "--commit-sha",
                release_commit,
                "--repository-root",
                str(repository_root),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("release tag must use hangar-v", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_github_output_is_allowlisted_and_single_line(self):
        metadata = release_metadata.build_release_metadata(
            event_name="push",
            ref_name="hangar-v0.1.0-rc.1",
            commit_sha=VALID_COMMIT,
            upstream=VALID_UPSTREAM,
        )

        output = release_metadata.format_github_output(metadata)
        values = dict(line.split("=", 1) for line in output.splitlines())

        self.assertEqual(values["git_tag"], "hangar-v0.1.0-rc.1")
        self.assertEqual(values["is_prerelease"], "true")
        self.assertEqual(values["primary_tag"], "v0.1.0-rc.1")
        self.assertEqual(values["release_title"], "Hangar v0.1.0-rc.1")
        self.assertEqual(values["upstream_revision"], VALID_UPSTREAM.revision)
        self.assertNotIn("event_name", values)
        self.assertNotIn("schema_version", values)

        unsafe_metadata = replace(metadata, release_title="Hangar v0.1.0\nforged=true")
        with self.assertRaisesRegex(MetadataError, "control character"):
            release_metadata.format_github_output(unsafe_metadata)


if __name__ == "__main__":
    unittest.main()
