# Kubernetes security and artifact verification

This document explains the chart's security boundaries and provides commands for
verifying the public `0.1.0-rc.46` release.

## Security model

The chart assumes that the cluster, nodes, control plane, CNI, CSI driver,
ingress controller, secret-delivery system, and external stateful services are
trusted operator-managed infrastructure. The chart hardens Hangar workloads
inside that boundary; it cannot compensate for a compromised cluster
administrator, node, registry client, or dependency administrator.

The chart provides these controls:

- fixed non-root identities and Restricted-compatible Pod security contexts;
- read-only root filesystems;
- all Linux capabilities dropped;
- privilege escalation disabled;
- `RuntimeDefault` seccomp;
- no chart-created RBAC and no ServiceAccount token automounting;
- default-deny ingress and egress policies;
- pre-existing Secret references instead of Helm-generated credentials;
- immutable image digests in published chart packages;
- telemetry and release discovery disabled by default; and
- build provenance, SBOMs, GitHub attestations, and keyless Cosign signatures for
  release artifacts.

NetworkPolicy is defense in depth. It does not replace service-side TLS, cloud
firewalls, restrictive IAM, node isolation, or egress controls outside the CNI.

When Todoist imports are enabled, the chart renders a dedicated non-root,
read-only `import-worker` for the isolated `imports` queue. Only API and
import-capable workers receive the object-storage credential interface; the
private import bucket is never routed publicly. User/workspace throttles limit
request abuse with atomic Valkey/Redis counters shared by API replicas, while
PostgreSQL row-locked budgets enforce concurrent jobs, active source bytes, and
rolling rows independently of cache correctness. A throttle-store outage fails
closed before CSV parsing or source retention.
Append-only audit events record safe admission and transition metadata without
CSV rows, filenames, mappings, object keys, source digests, or raw exceptions.

These controls do not make imported data trusted. Per-row authorization,
manifest drift checks, lease fencing, database idempotency constraints, bounded
retention, and private-bucket policy remain required. Operators must keep API,
import-worker, and Beat on the same validated configuration and treat disabling
`todoistImports.enabled` as the supported containment control.

## Secret containment

Secret values must enter the namespace through a secret manager or a controlled
Kubernetes Secret workflow. They must not be supplied with Helm `--set`, stored
in a values file, committed to Git, or attached to support reports.

The chart receives only resource and key names in ordinary values. Workloads use
`secretKeyRef` or mounted Secret volumes. The chart does not request permission
to read Secrets through the Kubernetes API.

`LIVE_SERVER_SECRET_KEY` is shared only with Live and the general worker. It
authenticates the worker's document-conversion call; API, Beat, mail, import,
frontend, and migration workloads do not receive it.

Kubernetes Secrets are not encrypted by default in every cluster. Enable and
govern control-plane encryption at rest, restrict API access, audit reads, and
control etcd backups according to the cluster's security baseline.

## Network boundaries

Only the selected ingress-controller Pods may reach public Hangar components.
PostgreSQL, Valkey, RabbitMQ, and evaluation object storage remain internal.

Application Pods may use DNS, in-release dependencies, explicitly configured
private CIDR/port pairs, and public HTTPS destinations that are not in private or
reserved ranges. This blocks common metadata-service and loopback SSRF targets at
the network layer. Application webhook destination validation remains a separate
control.

Live PDF image egress adds an application-layer boundary: all DNS answers are
classified, the socket is pinned to the checked address, redirect hops are
revalidated, and the renderer receives only bounded, re-encoded data URIs.
`live.pdfAssetAllowedHosts` is an explicit exception for exact, trusted private
storage hostnames and must remain empty when the storage URL is publicly
routable.

Verify the rendered selectors against real cluster labels. A policy object that
selects the wrong ingress or DNS Pods can fail closed and cause an outage; a CNI
that does not enforce policies can fail open.

## Release trust chain

For `0.1.0-rc.46`, the trust chain is:

1. signed Git tag `hangar-v0.1.0-rc.46` identifies the source commit;
2. the release workflow builds AMD64 images with BuildKit SBOM and provenance;
3. GitHub creates build-provenance attestations;
4. the workflow signs image and chart digests keylessly with GitHub OIDC;
5. the exact packaged chart passes the ephemeral evaluation qualification;
6. the chart is published to GHCR and attached to the GitHub Release; and
7. the release records the chart OCI digest and image digests.

Verification must use immutable digests and the exact workflow identity. A valid
signature for a different workflow, repository, tag, or issuer is not sufficient.

## Verify release `0.1.0-rc.46`

These commands require `curl`, `sha256sum`, GitHub CLI for the GitHub attestation,
and Cosign for OCI signatures.

### 1. Download public release assets

```bash
export VERSION=0.1.0-rc.46
export GIT_TAG=hangar-v0.1.0-rc.46
export RELEASE_URL="https://github.com/szymczag/hangar/releases/download/$GIT_TAG"

mkdir "hangar-$VERSION-release"
cd "hangar-$VERSION-release"

curl --fail --location --remote-name \
  "$RELEASE_URL/hangar-$VERSION.tgz"
curl --fail --location --remote-name \
  "$RELEASE_URL/hangar-$VERSION.tgz.sha256"
curl --fail --location --remote-name \
  "$RELEASE_URL/chart-oci-digest.txt"
```

### 2. Verify the archive checksum

```bash
sha256sum --check "hangar-$VERSION.tgz.sha256"
```

Compare the verified checksum with the digest displayed for the chart asset on
the GitHub Release page.

### 3. Verify the GitHub build-provenance attestation

Authenticate GitHub CLI to GitHub, then run:

```bash
gh attestation verify "hangar-$VERSION.tgz" \
  --repo szymczag/hangar
```

Review the subject digest and repository in the verification output; do not rely
only on the process exit code.

### 4. Verify the OCI chart signature

```bash
CHART_REF="$(cat chart-oci-digest.txt)"
IDENTITY="https://github.com/szymczag/hangar/.github/workflows/build-branch.yml@refs/tags/$GIT_TAG"

cosign verify \
  --certificate-identity "$IDENTITY" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  "$CHART_REF"
```

`chart-oci-digest.txt` must contain a digest-pinned
`ghcr.io/szymczag/charts/hangar@sha256:...` reference, never a mutable tag.

### 5. Verify the runtime image signatures

The chart uses five Hangar image families. Copy their complete digest-pinned
references from the GitHub Release notes into this array:

```bash
IMAGES=(
  ghcr.io/szymczag/hangar-web@sha256:REPLACE_WITH_RELEASE_DIGEST
  ghcr.io/szymczag/hangar-admin@sha256:REPLACE_WITH_RELEASE_DIGEST
  ghcr.io/szymczag/hangar-space@sha256:REPLACE_WITH_RELEASE_DIGEST
  ghcr.io/szymczag/hangar-live@sha256:REPLACE_WITH_RELEASE_DIGEST
  ghcr.io/szymczag/hangar-api@sha256:REPLACE_WITH_RELEASE_DIGEST
)

for image in "${IMAGES[@]}"; do
  cosign verify \
    --certificate-identity "$IDENTITY" \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com \
    "$image"
done
```

The GitHub Release notes record the proxy and AIO image digests as well. Those
images are release artifacts but are not used by the Kubernetes chart.

### 6. Confirm the archive embeds those digests

```bash
helm show values "hangar-$VERSION.tgz"
```

Inspect `web.image.digest`, `admin.image.digest`, `space.image.digest`,
`live.image.digest`, and `api.image.digest`. Each must match the release digest
above. An all-zero digest identifies an unstaged source chart and must be rejected.

### 7. Test anonymous registry access

The chart and Hangar images are public. Use a client configuration with no saved
registry credentials when this property matters to your deployment:

```bash
helm show chart oci://ghcr.io/szymczag/charts/hangar \
  --version "$VERSION"
```

For a full image-layer test with Podman:

```bash
AUTHFILE="$(mktemp)"
printf '{}\n' > "$AUTHFILE"
chmod 600 "$AUTHFILE"

for image in "${IMAGES[@]}"; do
  podman pull --platform linux/amd64 --authfile "$AUTHFILE" "$image"
done

rm -f "$AUTHFILE"
```

This checks more than manifest visibility: every selected AMD64 layer must be
downloadable without credentials.

## Evaluation dependency integrity

The chart vendors and locks its evaluation subcharts. Their archive hashes and
platform image digests are recorded in
[`DEPENDENCIES.md`](../../charts/hangar/DEPENDENCIES.md). Dependencies are not
covered by the Hangar Cosign identity; review their upstream provenance,
licenses, vulnerabilities, and maintenance status independently.

## Current limitations

`0.1.0-rc.46` is a prerelease. Only the evaluation profile has completed live
cluster qualification. Vulnerability and license approval, production security
qualification, backup/restore, migration-failure recovery, and the complete
support matrix remain open gates.

Artifact signatures prove which workflow produced an immutable digest. They do
not prove that the software is vulnerability-free, operationally supported, or
appropriate for a particular environment.
