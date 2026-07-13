# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SCRIPTS_DIRECTORY / "release_notes.py"
sys.path.insert(0, str(SCRIPTS_DIRECTORY))
SPEC = importlib.util.spec_from_file_location("release_notes", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load release_notes.py")
release_notes = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release_notes
SPEC.loader.exec_module(release_notes)

MetadataError = release_notes.MetadataError


CURATED_NOTES = """## Security and privacy

No security or privacy changes identified.

## Migrations and compatibility

No operator action is required.

## Known limitations and rollback

Database rollback requires a compatible backup.
"""


class CuratedNotesTests(unittest.TestCase):
    def test_loads_exact_namespaced_note_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            notes_directory = Path(temporary_directory)
            (notes_directory / "hangar-v0.1.0-rc.1.md").write_text(
                CURATED_NOTES,
                encoding="utf-8",
            )

            result = release_notes.load_curated_notes(notes_directory, "hangar-v0.1.0-rc.1")

        self.assertEqual(result, CURATED_NOTES.strip())

    def test_rejects_missing_empty_reordered_and_unnamespaced_notes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            notes_directory = Path(temporary_directory)
            with self.assertRaises(MetadataError):
                release_notes.load_curated_notes(notes_directory, "hangar-v0.1.0")
            with self.assertRaises(MetadataError):
                release_notes.load_curated_notes(notes_directory, "v0.1.0")

            invalid_notes = (
                CURATED_NOTES.replace("No operator action is required.", ""),
                CURATED_NOTES.replace(
                    "## Security and privacy",
                    "## Temporary",
                ),
                "\n\n".join(reversed(CURATED_NOTES.split("\n\n"))),
            )
            for index, content in enumerate(invalid_notes):
                tag = f"hangar-v0.1.{index}"
                (notes_directory / f"{tag}.md").write_text(content, encoding="utf-8")
                with self.subTest(index=index), self.assertRaises(MetadataError):
                    release_notes.load_curated_notes(notes_directory, tag)


class PreviousReleaseTests(unittest.TestCase):
    def test_selects_latest_published_namespaced_release(self):
        pages = [
            [
                {
                    "tag_name": "v1.3.1",
                    "draft": False,
                    "published_at": "2026-07-10T10:00:00Z",
                },
                {
                    "tag_name": "hangar-v0.1.0-alpha.1",
                    "draft": False,
                    "published_at": "2026-07-11T10:00:00Z",
                },
            ],
            [
                {
                    "tag_name": "hangar-v0.1.0-beta.1",
                    "draft": False,
                    "published_at": "2026-07-12T10:00:00Z",
                },
                {
                    "tag_name": "hangar-v9.0.0",
                    "draft": True,
                    "published_at": "2026-07-13T10:00:00Z",
                },
            ],
        ]

        previous = release_notes.select_previous_release(pages, "hangar-v0.1.0-rc.1")

        self.assertEqual(previous, "hangar-v0.1.0-beta.1")

    def test_returns_none_for_first_hangar_release(self):
        pages = [[{"tag_name": "v1.3.1", "draft": False, "published_at": "2026-07-10T10:00:00Z"}]]

        self.assertIsNone(release_notes.select_previous_release(pages, "hangar-v0.1.0-rc.1"))

    def test_rejects_malformed_namespaced_release_and_duplicate_tag(self):
        malformed = [
            {
                "tag_name": "hangar-v0.1.0-dev.1",
                "draft": False,
                "published_at": "2026-07-10T10:00:00Z",
            }
        ]
        with self.assertRaisesRegex(MetadataError, "invalid Hangar tag"):
            release_notes.select_previous_release(malformed, "hangar-v0.1.0")

        duplicate = [
            {
                "tag_name": "hangar-v0.1.0-alpha.1",
                "draft": False,
                "published_at": "2026-07-10T10:00:00Z",
            },
            {
                "tag_name": "hangar-v0.1.0-alpha.1",
                "draft": False,
                "published_at": "2026-07-11T10:00:00Z",
            },
        ]
        with self.assertRaisesRegex(MetadataError, "duplicate tag"):
            release_notes.select_previous_release(duplicate, "hangar-v0.1.0")


class DigestTests(unittest.TestCase):
    def test_requires_exact_image_set_and_sha256_digests(self):
        valid = {image: f"sha256:{index:064x}" for index, image in enumerate(release_notes.IMAGE_NAMES, 1)}
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "digests.json"
            path.write_text(json.dumps(valid), encoding="utf-8")
            self.assertEqual(release_notes.load_digests(path), valid)

            invalid = dict(valid)
            invalid.pop("aio")
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(MetadataError, "exactly the seven"):
                release_notes.load_digests(path)


class ReleaseNoteGenerationTests(unittest.TestCase):
    def git(self, repository: Path, *arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def commit(self, repository: Path, message: str):
        self.git(repository, "add", "UPSTREAM_BASE.json")
        self.git(repository, "commit", "-m", message)
        return self.git(repository, "rev-parse", "HEAD")

    def write_baseline(self, repository: Path, revision: str, synced_at: str):
        (repository / "UPSTREAM_BASE.json").write_text(
            json.dumps(
                {
                    "repository": "https://github.com/makeplane/plane",
                    "revision": revision,
                    "package_version": "1.3.1",
                    "synced_at": synced_at,
                }
            ),
            encoding="utf-8",
        )

    def test_generates_controlled_comparison_and_exact_digests(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            self.git(repository, "init", "--initial-branch=main")
            self.git(repository, "config", "user.name", "Release Note Tests")
            self.git(repository, "config", "user.email", "tests@example.invalid")
            self.git(repository, "config", "commit.gpgsign", "false")
            self.git(repository, "commit", "--allow-empty", "-m", "upstream baseline one")
            upstream_one = self.git(repository, "rev-parse", "HEAD")
            self.write_baseline(repository, upstream_one, "2026-07-01")
            first_release = self.commit(repository, "first Hangar release")
            self.git(repository, "tag", "hangar-v0.1.0", first_release)
            self.git(repository, "commit", "--allow-empty", "-m", "upstream baseline two")
            upstream_two = self.git(repository, "rev-parse", "HEAD")
            self.write_baseline(repository, upstream_two, "2026-07-10")
            current_commit = self.commit(repository, "prepare release candidate")
            release_pages = [
                {
                    "tag_name": "v1.3.1",
                    "draft": False,
                    "published_at": "2026-07-01T10:00:00Z",
                },
                {
                    "tag_name": "hangar-v0.1.0",
                    "draft": False,
                    "published_at": "2026-07-02T10:00:00Z",
                },
            ]
            digests = {
                image: f"sha256:{index:064x}"
                for index, image in enumerate(release_notes.IMAGE_NAMES, 1)
            }

            output = release_notes.generate_release_notes(
                repository_root=repository,
                current_tag="hangar-v0.2.0-rc.1",
                current_commit=current_commit,
                release_pages=release_pages,
                curated_notes=CURATED_NOTES.strip(),
                digests=digests,
            )

        self.assertIn("# Hangar v0.2.0-rc.1", output)
        self.assertIn("Changes since `hangar-v0.1.0`", output)
        self.assertIn(f"{upstream_one}...{upstream_two}", output)
        self.assertIn("prepare release candidate", output)
        self.assertIn(f"ghcr.io/szymczag/hangar-web@{digests['web']}", output)
        self.assertIn("refs/tags/hangar-v0.2.0-rc.1", output)
        self.assertIn("does not update the `stable` image tag", output)
        self.assertNotIn("Changes since `v1.3.1`", output)


if __name__ == "__main__":
    unittest.main()
