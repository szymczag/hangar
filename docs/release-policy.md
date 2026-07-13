# Hangar release and versioning policy

Status: approved on 2026-07-13.

## Purpose

This policy defines how Hangar versions, tags, publishes, and identifies releases
while continuing to merge changes from Plane. It applies to Git tags, GitHub
Releases, GHCR images, release notes, update discovery, and compatibility records.

Hangar versions describe Hangar's own stability and compatibility contract. Plane
versions remain upstream provenance, not Hangar product versions.

## Release identities

A release has several related identifiers. They are not interchangeable.

| Identifier        | Example                    | Meaning                                                        |
| ----------------- | -------------------------- | -------------------------------------------------------------- |
| Hangar version    | `v0.1.0-rc.1`              | Product version shown to users and stored in image metadata.   |
| Git tag           | `hangar-v0.1.0-rc.1`       | Immutable source marker that triggers the release workflow.    |
| GitHub Release    | `Hangar v0.1.0-rc.1`       | Notes and release assets associated with the Git tag.          |
| GHCR tag          | `v0.1.0-rc.1`              | Human-readable pointer inside a Hangar-owned image repository. |
| Source tag        | `sha-<full-hangar-commit>` | Immutable trace from an image to its Hangar source commit.     |
| Image digest      | `sha256:<digest>`          | Immutable identity of the published OCI image or index.        |
| Upstream revision | 40-character Git SHA       | Exact Plane commit incorporated into the release.              |

GitHub Releases are based on Git tags. Hangar therefore uses both: the tag records
the source revision, while the Release provides the supported distribution record,
notes, and assets. Production deployments must pin verified image digests even when
they use a version tag for discovery.

References:

- [GitHub: About releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
- [Semantic Versioning 2.0.0](https://semver.org/)
- [OCI Distribution Specification](https://github.com/opencontainers/distribution-spec/blob/main/spec.md)

## Tag namespace

Hangar Git tags must use this namespace:

```text
hangar-vMAJOR.MINOR.PATCH
hangar-vMAJOR.MINOR.PATCH-alpha.NUMBER
hangar-vMAJOR.MINOR.PATCH-beta.NUMBER
hangar-vMAJOR.MINOR.PATCH-rc.NUMBER
```

Examples:

```text
hangar-v0.1.0-alpha.1
hangar-v0.1.0-rc.1
hangar-v0.1.0
hangar-v0.1.1
hangar-v1.0.0
```

The `hangar-` prefix is part of the Git tag, not the product version. The release
workflow removes it before creating GHCR tags, setting `APP_VERSION`, and writing
the OCI version annotation.

Unnamespaced `v*` tags are reserved as upstream Plane reference points. The fork
already contains Plane tags such as `v1.3.1`, pointing to upstream commits rather
than Hangar release commits. Hangar must not delete, move, repurpose, or create
GitHub Releases from those tags. Maintainers must not push all locally fetched
upstream tags to `origin`; use an explicit branch push instead of `git push --tags`
or `git push --mirror`.

## Version semantics

Hangar follows Semantic Versioning according to Hangar's supported behavior:

- **Patch**: compatible bug fixes, security fixes, and compatible upstream syncs.
- **Minor**: backwards-compatible Hangar features, deployment capabilities, or
  substantial upstream functionality.
- **Major**: incompatible API, configuration, authentication, migration, data,
  or supported-deployment changes.
- **Prerelease**: an `alpha.N`, `beta.N`, or `rc.N` build that is not yet a stable
  supported release.

An upstream release does not automatically cause a Hangar release or determine the
Hangar version bump. The merged result must first pass Hangar's own compatibility,
security, installation, upgrade, and restore gates.

Until the project has completed its independence, installation, upgrade, restore,
security, and release-qualification milestones, Hangar releases remain `0.x`
and/or GitHub prereleases.

### Rejected schemes

| Scheme                             | Reason                                                                                              |
| ---------------------------------- | --------------------------------------------------------------------------------------------------- |
| `v1.3.1`                           | Already occupied by an upstream tag and falsely implies equivalence with Plane.                     |
| `v1.3.1-hangar.1`                  | SemVer treats it as a prerelease of Plane `1.3.1`; it cannot represent a normal Hangar stable line. |
| `v1.3.1+hangar.1`                  | Build metadata has no version precedence and `+` is unsuitable for the GHCR tag mapping.            |
| `v1.3.1.1`                         | Not Semantic Versioning.                                                                            |
| `hangar-v1.3.1` derived from Plane | Avoids a ref collision but still conflates Hangar stability with Plane's lifecycle.                 |

## Upstream provenance

Each Hangar release records an exact upstream commit independently of its Hangar
version. The root `UPSTREAM_BASE.json` file is the machine-readable source of
truth:

```json
{
  "repository": "https://github.com/makeplane/plane",
  "revision": "0000000000000000000000000000000000000000",
  "package_version": "1.3.1",
  "synced_at": "2026-07-13"
}
```

The `revision` is authoritative. `package_version` is informational because Plane
release tags may be created on a release lineage rather than directly on the
`preview` lineage merged by Hangar.

The baseline file must be updated in the pull request that merges upstream. The
release preflight must verify that:

1. the repository value is the expected Plane repository;
2. the revision is a complete lowercase SHA-1;
3. the revision exists in the checked-out Git object graph; and
4. the revision is an ancestor of the Hangar release commit.

Release notes and OCI metadata must include:

- Hangar version and Git revision;
- upstream repository and exact revision;
- upstream package version as informational context;
- a comparison with the previous Hangar release's upstream baseline; and
- migration or compatibility qualifications discovered during the sync.

Custom OCI labels use the Hangar GitHub namespace:

```text
io.github.szymczag.hangar.upstream.repository
io.github.szymczag.hangar.upstream.revision
io.github.szymczag.hangar.release.tag
```

The root `package.json` version may continue to follow upstream where that reduces
merge conflicts. It is not the Hangar release-version source of truth.

## Publication policy

### Stable releases

A stable release uses `hangar-vMAJOR.MINOR.PATCH`. It may update the mutable GHCR
`stable` tag only after every required image, signature, attestation, asset, and
publication check succeeds.

### Prereleases

A prerelease uses `hangar-vMAJOR.MINOR.PATCH-{alpha,beta,rc}.NUMBER`. It is marked
as a GitHub prerelease and must not update `stable`.

The first release-pipeline exercise will use:

```text
Git tag:        hangar-v0.1.0-rc.1
Product version: v0.1.0-rc.1
GitHub Release: Hangar v0.1.0-rc.1
GHCR tag:       v0.1.0-rc.1
```

### Preview publications

Manually dispatched `preview-*` images are development artifacts, not releases.
They have no Git tag or GitHub Release, do not update `stable`, and remain unsigned
by Cosign so a Cosign signature retains the meaning "approved release flow".
Preview source tags use `preview-sha-<full-hangar-commit>` so they cannot consume or
overwrite the immutable `sha-<full-hangar-commit>` namespace used by releases.

## Signing and immutability

Release tags are signed annotated Git tags created by the maintainer. Every release
image digest is then:

1. built with an SBOM and maximum BuildKit provenance;
2. attested with GitHub artifact attestations;
3. signed keylessly with Cosign through GitHub OIDC; and
4. immediately verified against the exact Hangar publication workflow and tag.

The publication workflow rejects lightweight tags, unverified annotated tags, and
tags that do not point directly to the workflow commit.

The expected certificate identity includes the namespaced tag:

```text
https://github.com/szymczag/hangar/.github/workflows/build-branch.yml@refs/tags/hangar-v0.1.0-rc.1
```

The expected issuer is:

```text
https://token.actions.githubusercontent.com
```

Published Git tags, version tags, image digests, release assets, signatures, and
GitHub Releases are immutable. The workflow must reject reuse before publication.
Repository tag rules should block updates and deletion of `hangar-v*`, and GitHub
immutable releases should be enabled when the repository setting is available.

## Release notes

Generated notes must compare only Hangar releases. Inherited Plane `v*` tags must
never be selected as the previous release. The workflow must explicitly identify
the previous published `hangar-v*` release or use a controlled first-release
baseline.

Every release note contains these sections:

1. Hangar changes since the previous Hangar release;
2. upstream Plane baseline and upstream changes incorporated;
3. security and privacy changes;
4. migrations and compatibility notes;
5. known limitations and rollback constraints;
6. release assets and image families; and
7. digest, provenance, SBOM, and Cosign verification instructions.

Security/privacy, migration/compatibility, and limitation/rollback content is
maintainer-reviewed in `docs/releases/<hangar-tag>.md` before the signed tag is
created. The workflow rejects a release when that exact file or any required
section is missing. Commit lists, upstream comparisons, exact image digests, and
verification commands are generated from the signed source, published Hangar
release records, and GHCR manifests; they are not copied from inherited Plane tags.

## One-shot release rule

A pushed release tag consumes that version. If publication partially succeeds or a
post-tag check fails, do not move the tag or overwrite published image tags. Diagnose
the failure and publish a new prerelease or patch version, such as `rc.2`.

Rerunning the same workflow is permitted only when its immutability checks prove it
cannot overwrite a partial publication. Until a safe resume design exists, the
default recovery is a new version.

Before pushing a tag, the maintainer runs the release preflight against the exact
`preview` commit. The preflight does not publish, create refs, or request an OIDC
signing certificate.

## Release qualification

A release candidate is complete only when recorded test evidence demonstrates:

- all seven AMD64 image families published under version and source tags;
- anonymous manifest and full-layer pulls;
- correct OCI source, version, license, and upstream labels;
- valid SBOM and GitHub provenance attestations;
- valid Cosign signatures with the exact tag identity;
- no `stable` movement for a prerelease;
- clean installation from release assets and pinned image digests;
- upgrade from the earliest supported version;
- backup and restore of database and uploaded assets; and
- release notes with accurate compatibility and rollback information.

Stable v1 additionally requires completed project-independence, security,
installation, upgrade, backup, restore, and operations criteria.
