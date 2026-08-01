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


class UpstreamTransitionReviewTests(unittest.TestCase):
    def valid_payload(self):
        return {
            "schema_version": 1,
            "reviews": [
                {
                    "release_tag": "hangar-v0.1.0-rc.21",
                    "previous_release_tag": "hangar-v0.1.0-rc.19",
                    "repository": "https://github.com/makeplane/plane",
                    "previous_revision": "1" * 40,
                    "current_revision": "2" * 40,
                    "rationale": "The exact non-linear upstream transition received maintainer review.",
                }
            ],
        }

    def test_loads_exact_review_schema(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "reviews.json"
            path.write_text(json.dumps(self.valid_payload()), encoding="utf-8")

            reviews = release_notes.load_upstream_transition_reviews(path)

        review = reviews["hangar-v0.1.0-rc.21"]
        self.assertEqual(review.previous_release_tag, "hangar-v0.1.0-rc.19")
        self.assertEqual(review.previous_revision, "1" * 40)
        self.assertEqual(review.current_revision, "2" * 40)

    def test_rejects_malformed_mismatched_and_duplicate_reviews(self):
        invalid_payloads = []

        extra_key = self.valid_payload()
        extra_key["unexpected"] = True
        invalid_payloads.append(extra_key)

        wrong_repository = self.valid_payload()
        wrong_repository["reviews"][0]["repository"] = "https://example.invalid/plane"
        invalid_payloads.append(wrong_repository)

        unsafe_rationale = self.valid_payload()
        unsafe_rationale["reviews"][0]["rationale"] = "reviewed\u2028with a hidden line"
        invalid_payloads.append(unsafe_rationale)

        identical_tags = self.valid_payload()
        identical_tags["reviews"][0]["previous_release_tag"] = "hangar-v0.1.0-rc.21"
        invalid_payloads.append(identical_tags)

        duplicate = self.valid_payload()
        duplicate["reviews"].append(dict(duplicate["reviews"][0]))
        invalid_payloads.append(duplicate)

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "reviews.json"
            for index, payload in enumerate(invalid_payloads):
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(index=index), self.assertRaises(MetadataError):
                    release_notes.load_upstream_transition_reviews(path)


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
                transition_reviews={},
            )

        self.assertIn("# Hangar v0.2.0-rc.1", output)
        self.assertIn("Changes since `hangar-v0.1.0`", output)
        self.assertIn(f"{upstream_one}...{upstream_two}", output)
        self.assertIn("prepare release candidate", output)
        self.assertIn(f"ghcr.io/szymczag/hangar-web@{digests['web']}", output)
        self.assertIn("refs/tags/hangar-v0.2.0-rc.1", output)
        self.assertIn("does not update the `stable` image tag", output)
        self.assertNotIn("Changes since `v1.3.1`", output)

    def test_requires_exact_review_for_non_linear_upstream_transition(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            self.git(repository, "init", "--initial-branch=main")
            self.git(repository, "config", "user.name", "Release Note Tests")
            self.git(repository, "config", "user.email", "tests@example.invalid")
            self.git(repository, "config", "commit.gpgsign", "false")
            self.git(repository, "commit", "--allow-empty", "-m", "shared upstream root")
            shared_root = self.git(repository, "rev-parse", "HEAD")

            self.git(repository, "checkout", "-b", "rewritten-upstream", shared_root)
            self.git(repository, "commit", "--allow-empty", "-m", "final upstream baseline")
            current_upstream = self.git(repository, "rev-parse", "HEAD")

            self.git(repository, "checkout", "main")
            self.git(repository, "commit", "--allow-empty", "-m", "release candidate baseline")
            previous_upstream = self.git(repository, "rev-parse", "HEAD")
            self.write_baseline(repository, previous_upstream, "2026-07-29")
            previous_release = self.commit(repository, "previous Hangar release")
            previous_tag = "hangar-v0.1.0-rc.19"
            self.git(repository, "tag", previous_tag, previous_release)

            self.git(repository, "merge", "--no-ff", "rewritten-upstream", "-m", "merge final upstream")
            self.write_baseline(repository, current_upstream, "2026-08-01")
            current_commit = self.commit(repository, "prepare recovered release")
            current_tag = "hangar-v0.1.0-rc.21"
            release_pages = [
                {
                    "tag_name": previous_tag,
                    "draft": False,
                    "published_at": "2026-07-30T10:00:00Z",
                }
            ]
            digests = {
                image: f"sha256:{index:064x}"
                for index, image in enumerate(release_notes.IMAGE_NAMES, 1)
            }

            generation_arguments = {
                "repository_root": repository,
                "current_tag": current_tag,
                "current_commit": current_commit,
                "release_pages": release_pages,
                "curated_notes": CURATED_NOTES.strip(),
                "digests": digests,
            }
            with self.assertRaisesRegex(MetadataError, "lack an exact maintainer review"):
                release_notes.generate_release_notes(
                    **generation_arguments,
                    transition_reviews={},
                )

            mismatched_review = release_notes.UpstreamTransitionReview(
                release_tag=current_tag,
                previous_release_tag=previous_tag,
                repository="https://github.com/makeplane/plane",
                previous_revision=current_upstream,
                current_revision=previous_upstream,
                rationale="This intentionally mismatched review must not authorize the transition.",
            )
            with self.assertRaisesRegex(MetadataError, "lack an exact maintainer review"):
                release_notes.generate_release_notes(
                    **generation_arguments,
                    transition_reviews={current_tag: mismatched_review},
                )

            exact_review = release_notes.UpstreamTransitionReview(
                release_tag=current_tag,
                previous_release_tag=previous_tag,
                repository="https://github.com/makeplane/plane",
                previous_revision=previous_upstream,
                current_revision=current_upstream,
                rationale="The exact rewritten upstream transition received maintainer review.",
            )
            output = release_notes.generate_release_notes(
                **generation_arguments,
                transition_reviews={current_tag: exact_review},
            )

        self.assertIn("maintainer-reviewed because the histories are not linear", output)
        self.assertIn(f"/commit/{previous_upstream}", output)
        self.assertIn(f"/commit/{current_upstream}", output)
        self.assertNotIn(f"/compare/{previous_upstream}...{current_upstream}", output)


if __name__ == "__main__":
    unittest.main()
