## Security and privacy

This release candidate retains Restricted Pod Security-compatible workloads,
fixed non-root identities, read-only root filesystems, default-deny
NetworkPolicies, pre-existing Secret interfaces, privacy-by-default application
configuration, immutable image digests, provenance attestations, and keyless
Cosign verification.

The chart uses no Service `externalIPs` field or `gitRepo` volume, the two
Kubernetes 1.36 changes relevant to its existing stable API surface. Production
security qualification remains incomplete, so this release candidate is not a
supported production deployment.

## Migrations and compatibility

`rc.4` expands the declared Kubernetes compatibility range from 1.30–1.35 to
1.30–1.36, including Kubernetes `v1.36.2`. CI renders and validates both profiles
against exact 1.36.2 schemas and uses a checksum-pinned `kubectl v1.36.2`. The live
evaluation qualification uses Kind 0.32.0's official digest-pinned Kubernetes
1.36.1 node image, the newest 1.36 image published by that Kind release.

This release does not introduce an application database migration or change the
Helm 4.2 or AMD64-only compatibility boundaries. Installations and upgrades
continue to run a revision-scoped migration Job. Operators must use
`--wait-for-jobs` and take a coordinated PostgreSQL and object-storage backup
before upgrading.

## Known limitations and rollback

Only the evaluation profile has completed live qualification. Production
installation, authenticated upload and background-task flows, coordinated backup
and restore, migration-failure recovery, vulnerability and license review, and
the supported external-service matrix remain open gates.

Helm rollback does not reverse database migrations or external-service changes.
Recover incompatible data changes from the coordinated pre-upgrade backup.
Evaluation PVCs remain retained after uninstall and require explicit operator
deletion. `rc.1` and `rc.2` remain consumed incomplete publications; `rc.3` is the
previous complete public release candidate.
