#!/usr/bin/env python3

# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Assemble the verifiable evidence attached to a Hangar GitHub Release.

The publication workflow calls each subcommand once, in order:

``resolve``      resolve every published image tag to its immutable index digest
``pin-compose``  pin the release Docker Compose file to those digests
``sboms``        extract and check the BuildKit SPDX SBOM of every image
``manifest``     write ``release-manifest.json`` describing the release
``checksums``    write ``SHA256SUMS`` over every release asset

Everything except the ``docker buildx imagetools`` calls is a pure function so it
can be tested against frozen registry output.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

from release_metadata import (
    MetadataError,
    load_upstream_base,
    parse_release_tag,
    validate_commit_sha,
)


MANIFEST_SCHEMA_VERSION = 1
HANGAR_REPOSITORY = "https://github.com/szymczag/hangar"
IMAGE_REGISTRY_NAMESPACE = "ghcr.io/szymczag"
IMAGE_PREFIX = f"{IMAGE_REGISTRY_NAMESPACE}/hangar-"
CHART_REPOSITORY = f"{IMAGE_REGISTRY_NAMESPACE}/charts/hangar"
IMAGE_NAMES = ("web", "admin", "space", "live", "api", "proxy", "aio")
EXPECTED_PLATFORMS = ("linux/amd64",)
WORKFLOW_PATH = ".github/workflows/build-branch.yml"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
CHECKSUMS_FILE = "SHA256SUMS"
CHECKSUMS_BUNDLE_FILE = "SHA256SUMS.sigstore.json"
MANIFEST_FILE = "release-manifest.json"

# Observed in the hangar-v0.1.0 SBOMs (syft via BuildKit): web 72, admin 72,
# space 666, live 768, api 220, proxy 201, aio 1750 packages. The minimums sit
# well below those counts so ordinary dependency churn passes, while an SBOM
# that scanned the wrong layer or an empty filesystem does not. The key
# packages identify what each image actually ships: web and admin are static
# bundles served by nginx, so React exists only in the images that run Node.
SBOM_POLICY: Mapping[str, tuple[int, tuple[str, ...]]] = {
    "web": (40, ("nginx",)),
    "admin": (40, ("nginx",)),
    "space": (300, ("react", "express")),
    "live": (350, ("@hocuspocus/server", "yjs")),
    "api": (100, ("django", "celery")),
    "proxy": (100, ("caddy",)),
    "aio": (800, ("django", "react", "@hocuspocus/server", "caddy", "supervisor")),
}

_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_ATTESTATION_TYPE = "attestation-manifest"
_INDEX_MEDIA_TYPES = {
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
}
# A Hangar image reference as the Compose template writes it, or one already
# pinned. The registry part is either the literal namespace or the
# DOCKERHUB_USER variable defaulting to it; the tag part is optional.
_COMPOSE_IMAGE_PATTERN = re.compile(
    r"(?P<registry>\$\{DOCKERHUB_USER:-ghcr\.io/szymczag\}|ghcr\.io/szymczag)"
    r"/hangar-(?P<component>[a-z0-9][a-z0-9-]*)"
    r"(?P<tag>:(?:\$\{APP_RELEASE(?::?-[^}]*)?\}|[A-Za-z0-9_][A-Za-z0-9_.-]*))?"
    r"(?P<digest>@sha256:[0-9a-f]{64})?"
)
# After pinning, any remaining ``/hangar-<name>`` without a digest, or any use
# of the registry variable, is a Hangar image the pattern above did not cover.
_UNPINNED_RESIDUE_PATTERN = re.compile(
    r"/hangar-[a-z0-9-]+(?![a-z0-9-]|@sha256:[0-9a-f]{64})|\$\{DOCKERHUB_USER"
)


class EvidenceError(MetadataError):
    """Raised when release evidence is missing, malformed, or inconsistent."""


# --------------------------------------------------------------------------- #
# Image resolution
# --------------------------------------------------------------------------- #


def _platform_name(platform: Any) -> str:
    if not isinstance(platform, dict):
        raise EvidenceError("image index entry has no platform")
    os_name = platform.get("os")
    architecture = platform.get("architecture")
    if not isinstance(os_name, str) or not isinstance(architecture, str):
        raise EvidenceError("image index platform must name an os and architecture")
    name = f"{os_name}/{architecture}"
    variant = platform.get("variant")
    if isinstance(variant, str) and variant:
        name = f"{name}/{variant}"
    return name


def parse_image_index(manifest: Any, *, image: str) -> dict[str, Any]:
    """Return the index digest and platforms from ``imagetools inspect .Manifest``.

    Every platform image must carry a BuildKit attestation manifest; that is
    where the SBOM and provenance live, so an image without one fails here
    rather than when its SBOM is extracted.
    """
    if not isinstance(manifest, dict):
        raise EvidenceError(f"{image}: image manifest must be a JSON object")
    digest = manifest.get("digest")
    if not isinstance(digest, str) or not _DIGEST_PATTERN.fullmatch(digest):
        raise EvidenceError(f"{image}: image index has no valid sha256 digest")
    if manifest.get("mediaType") not in _INDEX_MEDIA_TYPES:
        raise EvidenceError(f"{image}: expected an image index carrying attestations")
    entries = manifest.get("manifests")
    if not isinstance(entries, list) or not entries:
        raise EvidenceError(f"{image}: image index lists no manifests")

    platform_digests: dict[str, str] = {}
    attested: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise EvidenceError(f"{image}: image index entry must be an object")
        annotations = entry.get("annotations") or {}
        if annotations.get("vnd.docker.reference.type") == _ATTESTATION_TYPE:
            reference = annotations.get("vnd.docker.reference.digest")
            if isinstance(reference, str):
                attested.add(reference)
            continue
        platform = _platform_name(entry.get("platform"))
        if platform in platform_digests:
            raise EvidenceError(f"{image}: image index repeats platform {platform}")
        entry_digest = entry.get("digest")
        if not isinstance(entry_digest, str) or not _DIGEST_PATTERN.fullmatch(entry_digest):
            raise EvidenceError(f"{image}: {platform} manifest has no valid digest")
        platform_digests[platform] = entry_digest

    platforms = sorted(platform_digests)
    if tuple(platforms) != tuple(sorted(EXPECTED_PLATFORMS)):
        raise EvidenceError(
            f"{image}: published platforms {platforms} do not match {list(EXPECTED_PLATFORMS)}"
        )
    unattested = sorted(p for p, d in platform_digests.items() if d not in attested)
    if unattested:
        raise EvidenceError(f"{image}: no attestation manifest for {', '.join(unattested)}")
    return {"digest": digest, "platforms": platforms}


def build_image_records(
    indexes: Mapping[str, Any], *, version: str, image_prefix: str = IMAGE_PREFIX
) -> dict[str, dict[str, Any]]:
    if set(indexes) != set(IMAGE_NAMES):
        raise EvidenceError("image resolution must cover exactly the seven Hangar images")
    records: dict[str, dict[str, Any]] = {}
    for image in IMAGE_NAMES:
        parsed = parse_image_index(indexes[image], image=image)
        repository = f"{image_prefix}{image}"
        records[image] = {
            "name": f"hangar-{image}",
            "repository": repository,
            "tag": version,
            "digest": parsed["digest"],
            "ref": f"{repository}@{parsed['digest']}",
            "platforms": parsed["platforms"],
        }
    return records


def load_image_records(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvidenceError(f"cannot read image records: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EvidenceError("image records must be valid JSON") from exc
    if not isinstance(data, dict) or set(data) != set(IMAGE_NAMES):
        raise EvidenceError("image records must contain exactly the seven Hangar images")
    for image in IMAGE_NAMES:
        record = data[image]
        if not isinstance(record, dict):
            raise EvidenceError(f"{image}: image record must be an object")
        digest = record.get("digest")
        if not isinstance(digest, str) or not _DIGEST_PATTERN.fullmatch(digest):
            raise EvidenceError(f"{image}: image record has an invalid digest")
        if record.get("ref") != f"{record.get('repository')}@{digest}":
            raise EvidenceError(f"{image}: image record reference does not match its digest")
    return {image: data[image] for image in IMAGE_NAMES}


# --------------------------------------------------------------------------- #
# Compose pinning
# --------------------------------------------------------------------------- #


def _split_comment(line: str) -> tuple[str, str]:
    """Split a YAML line into content and a trailing ``#`` comment.

    Compose values in this file never contain a literal ``#``; a ``#`` that
    starts the line or follows whitespace begins a comment.
    """
    match = re.search(r"(^|\s)#", line)
    if match is None:
        return line, ""
    start = match.start() + len(match.group(1))
    return line[:start], line[start:]


def pin_compose(text: str, digests: Mapping[str, str], *, version: str, git_tag: str) -> str:
    """Rewrite every Hangar image reference to ``ghcr.io/szymczag/hangar-<c>@<digest>``.

    Matching is by pattern rather than position, so services, anchors, and
    comments may move without breaking the release. Unknown Hangar components,
    and any Hangar reference the pattern does not recognise, fail the release.
    """
    for image, digest in digests.items():
        if image not in IMAGE_NAMES or not _DIGEST_PATTERN.fullmatch(digest):
            raise EvidenceError(f"invalid digest for {image}")

    pinned_components: set[str] = set()
    output_lines: list[str] = []
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        content, comment = _split_comment(line)

        def replace(match: re.Match[str], number: int = number) -> str:
            component = match["component"]
            if component not in IMAGE_NAMES:
                raise EvidenceError(f"line {number}: unknown Hangar image hangar-{component}")
            if component not in digests:
                raise EvidenceError(f"line {number}: no digest resolved for hangar-{component}")
            pinned_components.add(component)
            return f"{IMAGE_PREFIX}{component}@{digests[component]}"

        content = _COMPOSE_IMAGE_PATTERN.sub(replace, content)
        residue = _UNPINNED_RESIDUE_PATTERN.search(content)
        if residue is not None:
            raise EvidenceError(
                f"line {number}: Hangar image reference left unpinned: {content.strip()}"
            )
        output_lines.append(content + comment)

    if not pinned_components:
        raise EvidenceError("compose file references no Hangar images")

    header = (
        f"# Hangar {version} ({git_tag}). The release workflow pinned every Hangar image\n"
        "# below to the digest it published and signed; APP_RELEASE and DOCKERHUB_USER\n"
        "# no longer select those images. Verify the digests against release-manifest.json.\n"
    )
    return header + "".join(output_lines)


# --------------------------------------------------------------------------- #
# SBOMs
# --------------------------------------------------------------------------- #


def extract_spdx_document(raw: Any, *, image: str, platform: str = EXPECTED_PLATFORMS[0]) -> dict[str, Any]:
    """Return the SPDX document from ``imagetools inspect --format '{{json .SBOM}}'``.

    A single-platform index yields ``{"SPDX": {...}}``; a multi-platform index
    yields ``{"<os>/<arch>": {"SPDX": {...}}}``. An in-toto statement whose
    predicate is the SPDX document is accepted too.
    """
    if not isinstance(raw, dict):
        raise EvidenceError(f"{image}: SBOM output must be a JSON object")
    if "SPDX" not in raw and platform in raw:
        raw = raw[platform]
        if not isinstance(raw, dict):
            raise EvidenceError(f"{image}: SBOM output for {platform} must be an object")
    document = raw.get("SPDX", raw)
    if isinstance(document, dict) and document.get("predicateType") == "https://spdx.dev/Document":
        document = document.get("predicate")
    if not isinstance(document, dict) or "spdxVersion" not in document:
        raise EvidenceError(f"{image}: no SPDX document in the image attestations")
    return document


def validate_spdx_document(document: Mapping[str, Any], *, image: str) -> dict[str, Any]:
    spdx_version = document.get("spdxVersion")
    if not isinstance(spdx_version, str) or not spdx_version.startswith("SPDX-2."):
        raise EvidenceError(f"{image}: unsupported SPDX version {spdx_version!r}")
    packages = document.get("packages")
    if not isinstance(packages, list):
        raise EvidenceError(f"{image}: SPDX document lists no packages")
    minimum, key_packages = SBOM_POLICY[image]
    if len(packages) < minimum:
        raise EvidenceError(
            f"{image}: SBOM lists {len(packages)} packages, fewer than the {minimum} expected"
        )
    names = {package.get("name") for package in packages if isinstance(package, dict)}
    missing = [name for name in key_packages if name not in names]
    if missing:
        raise EvidenceError(f"{image}: SBOM is missing key packages: {', '.join(missing)}")
    return {"format": spdx_version, "packages": len(packages)}


def sbom_file_name(image: str) -> str:
    return f"hangar-{image}.spdx.json"


def serialize_spdx_document(document: Mapping[str, Any]) -> bytes:
    return (json.dumps(document, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


# --------------------------------------------------------------------------- #
# Manifest and checksums
# --------------------------------------------------------------------------- #


def certificate_identity(git_tag: str) -> str:
    return f"{HANGAR_REPOSITORY}/{WORKFLOW_PATH}@refs/tags/{git_tag}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_release_manifest(
    *,
    git_tag: str,
    commit_sha: str,
    upstream: Mapping[str, str],
    images: Mapping[str, Mapping[str, Any]],
    sboms: Mapping[str, Mapping[str, Any]],
    chart_digest: str,
    chart_package_name: str,
    chart_package_sha256: str,
) -> dict[str, Any]:
    version, is_prerelease = parse_release_tag(git_tag)
    commit_sha = validate_commit_sha(commit_sha, field_name="release commit")
    if not _DIGEST_PATTERN.fullmatch(chart_digest):
        raise EvidenceError("chart digest must be a sha256 OCI digest")
    chart_version = version.removeprefix("v")
    if chart_package_name != f"hangar-{chart_version}.tgz":
        raise EvidenceError(f"chart package {chart_package_name} does not match {chart_version}")
    if set(images) != set(IMAGE_NAMES) or set(sboms) != set(IMAGE_NAMES):
        raise EvidenceError("manifest must describe exactly the seven Hangar images")

    image_entries = []
    for image in IMAGE_NAMES:
        record = images[image]
        if record.get("tag") != version:
            raise EvidenceError(f"{image}: resolved tag {record.get('tag')} is not {version}")
        image_entries.append(
            {
                "name": record["name"],
                "repository": record["repository"],
                "tag": record["tag"],
                "digest": record["digest"],
                "ref": record["ref"],
                "platforms": list(record["platforms"]),
                "sbom": dict(sboms[image]),
            }
        )

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "product": "hangar",
        "version": version,
        "prerelease": is_prerelease,
        "git_tag": git_tag,
        "source": {"repository": HANGAR_REPOSITORY, "commit": commit_sha},
        "upstream": dict(upstream),
        "images": image_entries,
        "chart": {
            "name": "hangar",
            "version": chart_version,
            "oci_ref": f"oci://{CHART_REPOSITORY}",
            "digest": chart_digest,
            "ref": f"{CHART_REPOSITORY}@{chart_digest}",
            "package": {"file": chart_package_name, "sha256": chart_package_sha256},
        },
        "verification": {
            "certificate_identity": certificate_identity(git_tag),
            "certificate_oidc_issuer": OIDC_ISSUER,
            "checksums": CHECKSUMS_FILE,
            "checksums_bundle": CHECKSUMS_BUNDLE_FILE,
        },
    }


def format_checksums(entries: Mapping[str, str]) -> str:
    """Format ``sha256sum``-compatible lines sorted by file name."""
    lines = []
    for name in sorted(entries):
        if "/" in name or "\n" in name or name in (CHECKSUMS_FILE, CHECKSUMS_BUNDLE_FILE):
            raise EvidenceError(f"cannot list {name!r} in {CHECKSUMS_FILE}")
        lines.append(f"{entries[name]}  {name}\n")
    if not lines:
        raise EvidenceError("no release assets to checksum")
    return "".join(lines)


def collect_checksums(directory: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for path in sorted(directory.iterdir()):
        if path.name in (CHECKSUMS_FILE, CHECKSUMS_BUNDLE_FILE):
            continue
        if path.is_symlink() or not path.is_file():
            raise EvidenceError(f"release assets must be regular files: {path.name}")
        entries[path.name] = sha256_file(path)
    return entries


# --------------------------------------------------------------------------- #
# Registry access (the only side effects besides writing files)
# --------------------------------------------------------------------------- #


Inspector = Callable[[str, str], Any]


def imagetools_inspect(reference: str, template: str, *, attempts: int = 3) -> Any:
    command = ["docker", "buildx", "imagetools", "inspect", reference, "--format", template]
    for attempt in range(1, attempts + 1):
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise EvidenceError(f"{reference}: imagetools returned invalid JSON") from exc
        if attempt == attempts:
            raise EvidenceError(
                f"{reference}: imagetools inspect failed: {result.stderr.strip()}"
            )
        time.sleep(attempt * 10)
    raise AssertionError("unreachable")


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command_resolve(arguments: argparse.Namespace, inspect: Inspector) -> None:
    version, _ = parse_release_tag(arguments.git_tag)
    indexes = {
        image: inspect(f"{IMAGE_PREFIX}{image}:{version}", "{{json .Manifest}}")
        for image in IMAGE_NAMES
    }
    records = build_image_records(indexes, version=version)
    _write_json(arguments.images_output, records)
    _write_json(arguments.digests_output, {image: records[image]["digest"] for image in IMAGE_NAMES})


def command_pin_compose(arguments: argparse.Namespace) -> None:
    version, _ = parse_release_tag(arguments.git_tag)
    records = load_image_records(arguments.images)
    text = arguments.compose.read_text(encoding="utf-8")
    pinned = pin_compose(
        text,
        {image: record["digest"] for image, record in records.items()},
        version=version,
        git_tag=arguments.git_tag,
    )
    arguments.compose.write_text(pinned, encoding="utf-8")


def command_sboms(arguments: argparse.Namespace, inspect: Inspector) -> None:
    records = load_image_records(arguments.images)
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    for image in IMAGE_NAMES:
        raw = inspect(records[image]["ref"], "{{json .SBOM}}")
        document = extract_spdx_document(raw, image=image)
        summary = validate_spdx_document(document, image=image)
        (arguments.output_dir / sbom_file_name(image)).write_bytes(serialize_spdx_document(document))
        print(f"{image}: {summary['format']} with {summary['packages']} packages")


def command_manifest(arguments: argparse.Namespace) -> None:
    records = load_image_records(arguments.images)
    sboms: dict[str, dict[str, Any]] = {}
    for image in IMAGE_NAMES:
        path = arguments.sbom_dir / sbom_file_name(image)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EvidenceError(f"{image}: cannot read SBOM {path}") from exc
        summary = validate_spdx_document(document, image=image)
        sboms[image] = {"file": path.name, "sha256": sha256_file(path), **summary}
    upstream = load_upstream_base(arguments.upstream_base)
    manifest = build_release_manifest(
        git_tag=arguments.git_tag,
        commit_sha=arguments.commit_sha,
        upstream={
            "repository": upstream.repository,
            "revision": upstream.revision,
            "package_version": upstream.package_version,
            "synced_at": upstream.synced_at,
        },
        images=records,
        sboms=sboms,
        chart_digest=arguments.chart_digest,
        chart_package_name=arguments.chart_package.name,
        chart_package_sha256=sha256_file(arguments.chart_package),
    )
    _write_json(arguments.output, manifest)


def command_checksums(arguments: argparse.Namespace) -> None:
    output = arguments.directory / CHECKSUMS_FILE
    output.write_text(format_checksums(collect_checksums(arguments.directory)), encoding="utf-8")


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve = subparsers.add_parser("resolve")
    resolve.add_argument("--git-tag", required=True)
    resolve.add_argument("--images-output", type=Path, required=True)
    resolve.add_argument("--digests-output", type=Path, required=True)

    pin = subparsers.add_parser("pin-compose")
    pin.add_argument("--git-tag", required=True)
    pin.add_argument("--images", type=Path, required=True)
    pin.add_argument("--compose", type=Path, required=True)

    sboms = subparsers.add_parser("sboms")
    sboms.add_argument("--images", type=Path, required=True)
    sboms.add_argument("--output-dir", type=Path, required=True)

    manifest = subparsers.add_parser("manifest")
    manifest.add_argument("--git-tag", required=True)
    manifest.add_argument("--commit-sha", required=True)
    manifest.add_argument("--upstream-base", type=Path, required=True)
    manifest.add_argument("--images", type=Path, required=True)
    manifest.add_argument("--sbom-dir", type=Path, required=True)
    manifest.add_argument("--chart-package", type=Path, required=True)
    manifest.add_argument("--chart-digest", required=True)
    manifest.add_argument("--output", type=Path, required=True)

    checksums = subparsers.add_parser("checksums")
    checksums.add_argument("--directory", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None, inspect: Inspector = imagetools_inspect) -> int:
    arguments = create_argument_parser().parse_args(argv)
    try:
        if arguments.command == "resolve":
            command_resolve(arguments, inspect)
        elif arguments.command == "pin-compose":
            command_pin_compose(arguments)
        elif arguments.command == "sboms":
            command_sboms(arguments, inspect)
        elif arguments.command == "manifest":
            command_manifest(arguments)
        else:
            command_checksums(arguments)
    except (MetadataError, OSError) as exc:
        print(f"release evidence error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
