## Security and privacy

This release candidate retains the Restricted Pod Security-compatible workloads,
fixed non-root identities, read-only root filesystems, default-deny
NetworkPolicies, pre-existing Secret interfaces, privacy-by-default application
configuration, immutable image digests, provenance attestations, and keyless
Cosign verification introduced for the Hangar-owned Helm chart.

The exact `rc.3` chart archive must pass the complete AMD64 ephemeral-cluster
qualification before publication. Production security qualification remains
incomplete, so this release candidate is not a supported production deployment.

## Migrations and compatibility

`rc.3` supplies the authenticated GHCR token required when the final release job
pulls the already-qualified chart into the GitHub Release asset set. It does not
introduce a database migration or change the chart's Kubernetes 1.30 through
1.35, Helm 4.2, or AMD64-only compatibility boundaries.

Installations and upgrades continue to run a revision-scoped migration Job.
Operators must use `--wait-for-jobs` and take a coordinated PostgreSQL and object
storage backup before upgrading. The evaluation profile remains intended for a
new, dedicated namespace and does not define an in-place migration from the
upstream `plane-ce` chart.

## Known limitations and rollback

`rc.1` completed live qualification and pushed an OCI chart, but stopped before
chart signing because its workflow did not capture Helm's stderr digest output.
`rc.2` completed live qualification, OCI publication, provenance, signing, and
signature verification, but stopped before GitHub Release creation because the
asset-staging step lacked its GHCR token environment variable. Both immutable
versions are consumed and must not be used as released Hangar charts. `rc.3` is
the replacement release candidate.

Only the evaluation profile has completed live qualification. Production install,
authenticated upload and background-task flows, coordinated backup and restore,
migration-failure recovery, vulnerability and license review, public-distribution
verification, and the supported-version matrix remain open gates.

Helm rollback does not reverse database migrations or external-service changes.
Recover incompatible data changes from the coordinated pre-upgrade backup.
Evaluation PVCs remain retained after uninstall and require explicit operator
deletion.
