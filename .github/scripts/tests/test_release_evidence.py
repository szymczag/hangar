# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = SCRIPTS_DIRECTORY / "release_evidence.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "release_evidence"
COMPOSE_PATH = REPOSITORY_ROOT / "deployments" / "cli" / "community" / "docker-compose.yml"
sys.path.insert(0, str(SCRIPTS_DIRECTORY))
SPEC = importlib.util.spec_from_file_location("release_evidence", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load release_evidence.py")
release_evidence = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release_evidence
SPEC.loader.exec_module(release_evidence)

EvidenceError = release_evidence.EvidenceError
GIT_TAG = "hangar-v0.2.0"
VERSION = "v0.2.0"
COMMIT = "d77325cf1e9f28f3119fe7fa21c3d4d8f6f90707"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fake_digest(index: int) -> str:
    return f"sha256:{index:064x}"


DIGESTS = {image: fake_digest(index) for index, image in enumerate(release_evidence.IMAGE_NAMES, 1)}


def index_for(digest: str, *, platform_digest: str | None = None) -> dict:
    """Shape an ``imagetools inspect .Manifest`` index like the captured fixture."""
    index = load_fixture("api-imagetools-manifest.json")
    index["digest"] = digest
    if platform_digest is not None:
        index["manifests"][0]["digest"] = platform_digest
        index["manifests"][1]["annotations"]["vnd.docker.reference.digest"] = platform_digest
    return index


def sbom_for(image: str) -> dict:
    """Pad the captured API SBOM to satisfy an image's policy."""
    raw = load_fixture("api-imagetools-sbom.json")
    minimum, key_packages = release_evidence.SBOM_POLICY[image]
    packages = raw["SPDX"]["packages"]
    packages.extend({"name": name, "SPDXID": f"SPDXRef-key-{index}"} for index, name in enumerate(key_packages))
    packages.extend(
        {"name": f"filler-{index}", "SPDXID": f"SPDXRef-filler-{index}"}
        for index in range(max(0, minimum + 10 - len(packages)))
    )
    return raw


class ImageIndexTests(unittest.TestCase):
    def test_parses_captured_single_platform_index(self):
        parsed = release_evidence.parse_image_index(
            load_fixture("api-imagetools-manifest.json"), image="api"
        )
        self.assertEqual(
            parsed,
            {
                "digest": "sha256:2abcf37120a62f3cfc12bd64ac36d26098dc404aedcb19c645d38683512c76e6",
                "platforms": ["linux/amd64"],
            },
        )

    def test_rejects_index_without_attestations(self):
        index = load_fixture("api-imagetools-manifest.json")
        index["manifests"] = index["manifests"][:1]
        with self.assertRaisesRegex(EvidenceError, "no attestation manifest"):
            release_evidence.parse_image_index(index, image="api")

    def test_rejects_attestation_for_a_different_image(self):
        index = load_fixture("api-imagetools-manifest.json")
        index["manifests"][1]["annotations"]["vnd.docker.reference.digest"] = fake_digest(9)
        with self.assertRaisesRegex(EvidenceError, "no attestation manifest"):
            release_evidence.parse_image_index(index, image="api")

    def test_rejects_unexpected_platforms_and_plain_manifests(self):
        index = load_fixture("api-imagetools-manifest.json")
        index["manifests"][0]["platform"]["architecture"] = "arm64"
        with self.assertRaisesRegex(EvidenceError, "do not match"):
            release_evidence.parse_image_index(index, image="api")

        index = load_fixture("api-imagetools-manifest.json")
        index["mediaType"] = "application/vnd.oci.image.manifest.v1+json"
        with self.assertRaisesRegex(EvidenceError, "image index"):
            release_evidence.parse_image_index(index, image="api")

        index = load_fixture("api-imagetools-manifest.json")
        index["digest"] = "sha256:short"
        with self.assertRaisesRegex(EvidenceError, "valid sha256"):
            release_evidence.parse_image_index(index, image="api")

    def test_builds_records_for_exactly_the_seven_images(self):
        indexes = {image: index_for(digest) for image, digest in DIGESTS.items()}
        records = release_evidence.build_image_records(indexes, version=VERSION)
        self.assertEqual(list(records), list(release_evidence.IMAGE_NAMES))
        self.assertEqual(
            records["proxy"],
            {
                "name": "hangar-proxy",
                "repository": "ghcr.io/szymczag/hangar-proxy",
                "tag": VERSION,
                "digest": DIGESTS["proxy"],
                "ref": f"ghcr.io/szymczag/hangar-proxy@{DIGESTS['proxy']}",
                "platforms": ["linux/amd64"],
            },
        )
        del indexes["aio"]
        with self.assertRaisesRegex(EvidenceError, "exactly the seven"):
            release_evidence.build_image_records(indexes, version=VERSION)


class ComposePinningTests(unittest.TestCase):
    TEMPLATE = (
        "services:\n"
        "  web:\n"
        "    image: ${DOCKERHUB_USER:-ghcr.io/szymczag}/hangar-web:${APP_RELEASE:-stable}\n"
        "  worker:\n"
        '    image: "${DOCKERHUB_USER:-ghcr.io/szymczag}/hangar-api:${APP_RELEASE:-stable}" # worker\n'
        "  proxy:\n"
        "    image: ghcr.io/szymczag/hangar-proxy:v0.1.0\n"
        "  db:\n"
        "    image: docker.io/library/postgres:15.7-alpine@sha256:" + "a" * 64 + "\n"
        "x-api-image: &api-image ghcr.io/szymczag/hangar-api\n"
        "# docs mention ${DOCKERHUB_USER:-ghcr.io/szymczag}/hangar-web:${APP_RELEASE:-stable}\n"
    )

    def pin(self, text: str) -> str:
        return release_evidence.pin_compose(text, DIGESTS, version=VERSION, git_tag=GIT_TAG)

    def test_pins_every_hangar_reference_form(self):
        pinned = self.pin(self.TEMPLATE)
        self.assertIn(f"    image: ghcr.io/szymczag/hangar-web@{DIGESTS['web']}\n", pinned)
        self.assertIn(f'    image: "ghcr.io/szymczag/hangar-api@{DIGESTS["api"]}" # worker\n', pinned)
        self.assertIn(f"    image: ghcr.io/szymczag/hangar-proxy@{DIGESTS['proxy']}\n", pinned)
        self.assertIn(f"&api-image ghcr.io/szymczag/hangar-api@{DIGESTS['api']}\n", pinned)
        self.assertIn("postgres:15.7-alpine@sha256:" + "a" * 64, pinned)
        self.assertNotIn("APP_RELEASE:-stable}\n    ", pinned)

    def test_records_the_release_and_leaves_comments_alone(self):
        pinned = self.pin(self.TEMPLATE)
        self.assertTrue(pinned.startswith(f"# Hangar {VERSION} ({GIT_TAG})."))
        self.assertIn(
            "# docs mention ${DOCKERHUB_USER:-ghcr.io/szymczag}/hangar-web:${APP_RELEASE:-stable}\n",
            pinned,
        )

    def test_is_idempotent_for_a_pinned_file(self):
        pinned = self.pin(self.TEMPLATE)
        body = pinned.split("\n", 3)[3]
        self.assertEqual(self.pin(body), pinned)

    def test_rejects_unknown_components(self):
        with self.assertRaisesRegex(EvidenceError, "unknown Hangar image hangar-worker"):
            self.pin("    image: ghcr.io/szymczag/hangar-worker:${APP_RELEASE:-stable}\n")

    def test_rejects_hangar_references_it_cannot_pin(self):
        for line in (
            "    image: ${DOCKERHUB_USER:-docker.io/other}/hangar-api:stable\n",
            "    image: registry.example/hangar-api:latest\n",
            "    image: ${DOCKERHUB_USER}/hangar-api:latest\n",
        ):
            with self.subTest(line=line):
                with self.assertRaisesRegex(EvidenceError, "left unpinned"):
                    self.pin("services:\n" + line)

    def test_rejects_a_file_without_hangar_images(self):
        with self.assertRaisesRegex(EvidenceError, "no Hangar images"):
            self.pin("services:\n  db:\n    image: postgres:15\n")

    def test_pins_the_repository_compose_file(self):
        # The release rewrites this file after the tag is pushed, where a
        # failure consumes the version; run the same rewrite at review time.
        source = COMPOSE_PATH.read_text(encoding="utf-8")
        pinned = self.pin(source)
        expected = {
            image
            for image in release_evidence.IMAGE_NAMES
            if f"/hangar-{image}:" in source
        }
        self.assertEqual(expected, {"web", "admin", "space", "live", "api", "proxy"})
        for image in expected:
            self.assertIn(f"image: ghcr.io/szymczag/hangar-{image}@{DIGESTS[image]}", pinned)
        self.assertNotIn("${APP_RELEASE", pinned.split("\n", 3)[3])
        self.assertNotIn("${DOCKERHUB_USER", pinned.split("\n", 3)[3])
        self.assertEqual(len(pinned.splitlines()), len(source.splitlines()) + 3)


class SbomTests(unittest.TestCase):
    def test_extracts_captured_single_platform_output(self):
        document = release_evidence.extract_spdx_document(
            load_fixture("api-imagetools-sbom.json"), image="api"
        )
        self.assertEqual(document["spdxVersion"], "SPDX-2.3")
        self.assertIn("django", {package["name"] for package in document["packages"]})

    def test_extracts_multi_platform_and_in_toto_shapes(self):
        document = load_fixture("api-imagetools-sbom.json")["SPDX"]
        self.assertIs(
            release_evidence.extract_spdx_document({"linux/amd64": {"SPDX": document}}, image="api"),
            document,
        )
        statement = {"predicateType": "https://spdx.dev/Document", "predicate": document}
        self.assertIs(release_evidence.extract_spdx_document(statement, image="api"), document)
        with self.assertRaisesRegex(EvidenceError, "no SPDX document"):
            release_evidence.extract_spdx_document({"linux/arm64": {"SPDX": document}}, image="api")
        with self.assertRaisesRegex(EvidenceError, "no SPDX document"):
            release_evidence.extract_spdx_document({}, image="api")

    def test_every_image_policy_accepts_a_conforming_document(self):
        for image in release_evidence.IMAGE_NAMES:
            with self.subTest(image=image):
                document = release_evidence.extract_spdx_document(sbom_for(image), image=image)
                summary = release_evidence.validate_spdx_document(document, image=image)
                self.assertEqual(summary["format"], "SPDX-2.3")
                self.assertGreaterEqual(summary["packages"], release_evidence.SBOM_POLICY[image][0])

    def test_rejects_thin_documents_and_missing_key_packages(self):
        document = load_fixture("api-imagetools-sbom.json")["SPDX"]
        with self.assertRaisesRegex(EvidenceError, "fewer than the 100 expected"):
            release_evidence.validate_spdx_document(document, image="api")

        document = sbom_for("api")["SPDX"]
        document["packages"] = [p for p in document["packages"] if p["name"] != "django"]
        with self.assertRaisesRegex(EvidenceError, "missing key packages: django"):
            release_evidence.validate_spdx_document(document, image="api")

        document = sbom_for("api")["SPDX"]
        document["spdxVersion"] = "SPDX-3.0"
        with self.assertRaisesRegex(EvidenceError, "unsupported SPDX version"):
            release_evidence.validate_spdx_document(document, image="api")

    def test_policy_covers_every_image(self):
        self.assertEqual(set(release_evidence.SBOM_POLICY), set(release_evidence.IMAGE_NAMES))


class ManifestTests(unittest.TestCase):
    UPSTREAM = {
        "repository": "https://github.com/makeplane/plane",
        "revision": "917b23a6c16d93fc00cef67900eff2755e8b13f7",
        "package_version": "1.4.0",
        "synced_at": "2026-08-01",
    }

    def records(self) -> dict:
        indexes = {image: index_for(digest) for image, digest in DIGESTS.items()}
        return release_evidence.build_image_records(indexes, version=VERSION)

    def sboms(self) -> dict:
        return {
            image: {"file": f"hangar-{image}.spdx.json", "sha256": "0" * 64, "format": "SPDX-2.3", "packages": 500}
            for image in release_evidence.IMAGE_NAMES
        }

    def build(self, **overrides):
        arguments = {
            "git_tag": GIT_TAG,
            "commit_sha": COMMIT,
            "upstream": self.UPSTREAM,
            "images": self.records(),
            "sboms": self.sboms(),
            "chart_digest": fake_digest(42),
            "chart_package_name": "hangar-0.2.0.tgz",
            "chart_package_sha256": "1" * 64,
        }
        arguments.update(overrides)
        return release_evidence.build_release_manifest(**arguments)

    def test_describes_release_images_chart_and_verification_policy(self):
        manifest = self.build()
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["version"], VERSION)
        self.assertFalse(manifest["prerelease"])
        self.assertEqual(manifest["source"], {"repository": "https://github.com/szymczag/hangar", "commit": COMMIT})
        self.assertEqual(manifest["upstream"], self.UPSTREAM)
        self.assertEqual(
            [image["name"] for image in manifest["images"]],
            [f"hangar-{image}" for image in release_evidence.IMAGE_NAMES],
        )
        api = manifest["images"][4]
        self.assertEqual(api["ref"], f"ghcr.io/szymczag/hangar-api@{DIGESTS['api']}")
        self.assertEqual(api["platforms"], ["linux/amd64"])
        self.assertEqual(api["sbom"]["file"], "hangar-api.spdx.json")
        self.assertEqual(
            manifest["chart"],
            {
                "name": "hangar",
                "version": "0.2.0",
                "oci_ref": "oci://ghcr.io/szymczag/charts/hangar",
                "digest": fake_digest(42),
                "ref": f"ghcr.io/szymczag/charts/hangar@{fake_digest(42)}",
                "package": {"file": "hangar-0.2.0.tgz", "sha256": "1" * 64},
            },
        )
        self.assertEqual(
            manifest["verification"],
            {
                "certificate_identity": (
                    "https://github.com/szymczag/hangar/.github/workflows/build-branch.yml"
                    "@refs/tags/hangar-v0.2.0"
                ),
                "certificate_oidc_issuer": "https://token.actions.githubusercontent.com",
                "checksums": "SHA256SUMS",
                "checksums_bundle": "SHA256SUMS.sigstore.json",
            },
        )

    def test_rejects_inconsistent_inputs(self):
        with self.assertRaises(release_evidence.MetadataError):
            self.build(git_tag="v0.2.0")
        with self.assertRaisesRegex(EvidenceError, "does not match"):
            self.build(chart_package_name="hangar-0.1.0.tgz")
        with self.assertRaisesRegex(EvidenceError, "chart digest"):
            self.build(chart_digest="sha256:nope")
        records = self.records()
        records["web"] = dict(records["web"], tag="v0.1.0")
        with self.assertRaisesRegex(EvidenceError, "is not v0.2.0"):
            self.build(images=records)
        sboms = self.sboms()
        del sboms["aio"]
        with self.assertRaisesRegex(EvidenceError, "exactly the seven"):
            self.build(sboms=sboms)


class ChecksumTests(unittest.TestCase):
    def test_formats_sorted_sha256sum_lines(self):
        text = release_evidence.format_checksums({"b.txt": "2" * 64, "a.txt": "1" * 64})
        self.assertEqual(text, f"{'1' * 64}  a.txt\n{'2' * 64}  b.txt\n")
        with self.assertRaises(EvidenceError):
            release_evidence.format_checksums({"SHA256SUMS": "1" * 64})
        with self.assertRaises(EvidenceError):
            release_evidence.format_checksums({})

    def test_checksums_verify_with_sha256sum_and_skip_signature_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            (directory / "setup.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            (directory / "release-manifest.json").write_text("{}\n", encoding="utf-8")
            (directory / "SHA256SUMS.sigstore.json").write_text("{}", encoding="utf-8")
            self.assertEqual(release_evidence.main(["checksums", "--directory", str(directory)]), 0)
            sums = (directory / "SHA256SUMS").read_text(encoding="utf-8")
            self.assertEqual(
                sums,
                f"{hashlib.sha256(b'{}' + bytes([10])).hexdigest()}  release-manifest.json\n"
                f"{hashlib.sha256(b'#!/bin/sh' + bytes([10])).hexdigest()}  setup.sh\n",
            )
            result = subprocess.run(
                ["sha256sum", "--check", "--strict", "SHA256SUMS"],
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_nested_directories(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            (directory / "sbom").mkdir()
            with self.assertRaisesRegex(EvidenceError, "regular files"):
                release_evidence.collect_checksums(directory)


class CommandLineTests(unittest.TestCase):
    def test_full_evidence_pipeline_with_a_fake_registry(self):
        calls = []

        def inspect(reference: str, template: str):
            calls.append((reference, template))
            image = reference.split("/hangar-", 1)[1].split("@", 1)[0].split(":", 1)[0]
            if template == "{{json .Manifest}}":
                return index_for(DIGESTS[image], platform_digest=fake_digest(100 + len(calls)))
            return copy.deepcopy(sbom_for(image))

        with tempfile.TemporaryDirectory() as temporary_directory:
            work = Path(temporary_directory)
            assets = work / "release-assets"
            assets.mkdir()
            compose = assets / "docker-compose.yml"
            compose.write_text(COMPOSE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            chart = assets / "hangar-0.2.0.tgz"
            chart.write_bytes(b"chart")

            def run(*argv: str) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return release_evidence.main(list(argv), inspect=inspect)

            self.assertEqual(
                run(
                    "resolve",
                    "--git-tag", GIT_TAG,
                    "--images-output", str(work / "release-images.json"),
                    "--digests-output", str(work / "release-digests.json"),
                ),
                0,
            )
            self.assertEqual(
                [reference for reference, _ in calls],
                [f"ghcr.io/szymczag/hangar-{image}:{VERSION}" for image in release_evidence.IMAGE_NAMES],
            )
            self.assertEqual(json.loads((work / "release-digests.json").read_text()), DIGESTS)

            self.assertEqual(
                run(
                    "pin-compose",
                    "--git-tag", GIT_TAG,
                    "--images", str(work / "release-images.json"),
                    "--compose", str(compose),
                ),
                0,
            )
            self.assertIn(f"hangar-api@{DIGESTS['api']}", compose.read_text())

            calls.clear()
            self.assertEqual(
                run("sboms", "--images", str(work / "release-images.json"), "--output-dir", str(assets)),
                0,
            )
            self.assertEqual(
                [reference for reference, _ in calls],
                [f"ghcr.io/szymczag/hangar-{image}@{DIGESTS[image]}" for image in release_evidence.IMAGE_NAMES],
            )

            self.assertEqual(
                run(
                    "manifest",
                    "--git-tag", GIT_TAG,
                    "--commit-sha", COMMIT,
                    "--upstream-base", str(REPOSITORY_ROOT / "UPSTREAM_BASE.json"),
                    "--images", str(work / "release-images.json"),
                    "--sbom-dir", str(assets),
                    "--chart-package", str(chart),
                    "--chart-digest", fake_digest(42),
                    "--output", str(assets / "release-manifest.json"),
                ),
                0,
            )
            manifest = json.loads((assets / "release-manifest.json").read_text())
            aio_sbom = assets / "hangar-aio.spdx.json"
            self.assertEqual(
                manifest["images"][6]["sbom"]["sha256"],
                hashlib.sha256(aio_sbom.read_bytes()).hexdigest(),
            )
            self.assertEqual(manifest["chart"]["package"]["sha256"], hashlib.sha256(b"chart").hexdigest())

            self.assertEqual(run("checksums", "--directory", str(assets)), 0)
            listed = [line.split("  ", 1)[1] for line in (assets / "SHA256SUMS").read_text().splitlines()]
            self.assertEqual(
                listed,
                sorted(
                    ["docker-compose.yml", "hangar-0.2.0.tgz", "release-manifest.json"]
                    + [f"hangar-{image}.spdx.json" for image in release_evidence.IMAGE_NAMES]
                ),
            )

    def test_reports_errors_without_a_traceback(self):
        def inspect(reference: str, template: str):
            return {"mediaType": "application/vnd.oci.image.manifest.v1+json"}

        with tempfile.TemporaryDirectory() as temporary_directory:
            work = Path(temporary_directory)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = release_evidence.main(
                    [
                        "resolve",
                        "--git-tag", GIT_TAG,
                        "--images-output", str(work / "images.json"),
                        "--digests-output", str(work / "digests.json"),
                    ],
                    inspect=inspect,
                )
        self.assertEqual(status, 1)
        self.assertIn("web: image index has no valid sha256 digest", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
