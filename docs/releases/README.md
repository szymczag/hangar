# Curated release notes

Every Hangar release tag must have a reviewed file named exactly after the Git
tag, for example:

```text
docs/releases/hangar-v0.1.0-rc.1.md
```

The publication preflight validates this file before approval or container builds.
It must contain these headings once, in this order, with explicit content:

```markdown
## Security and privacy

Describe security fixes, privacy changes, and relevant residual risk. Write
"No security or privacy changes identified." when that is the reviewed result.

## Migrations and compatibility

Describe database/configuration changes and supported upgrade paths. State
explicitly when no operator action is required.

## Known limitations and rollback

Describe known limitations, rollback constraints, and data compatibility. State
explicitly when no additional limitation is known.
```

When an upgrade step tells Compose or Swarm operators to replace `setup.sh` (or
`swarm.sh`) by hand, give the same commands the script prints when it refuses
an upgrade: download the script, `SHA256SUMS` and `SHA256SUMS.sigstore.json`
into `hangar-vX.Y.Z/`, check them with `cosign verify-blob` and
`sha256sum --check`, and only then copy the script into place. Never tell
operators to `curl -o setup.sh` over the script they are running. `setup.sh
upgrade` on Compose leaves every service stopped, so the steps end with
`./setup.sh start`; "No operator action is required" is never true for a
Compose upgrade. Swarm's `upgrade` redeploys the stack itself. These commands
are an upgrade step, not the generated verification section the next paragraph
refers to.

Every Compose upgrade path starts with a backup: tell operators to run
`./setup.sh backup` while the services are running and to keep
`plane-app/plane.env` with it, before `./setup.sh upgrade`. Say plainly that
`setup.sh backup` copies the running database's data directory instead of
dumping it, so the copy is not guaranteed to be consistent, and point to the
`pg_dump` step in the
[Compose guide](../../deployments/cli/community/README.md#backup-data-docker-compose).
Swarm has no backup action; say that its volumes are backed up on the node that
holds them.

When a step uses `./setup.sh update-script`, say that it checks the Cosign
signature only when `cosign` is installed and otherwise warns, and that
`HANGAR_REQUIRE_SIGNATURE=1` makes the check mandatory.

Do not write that the Compose or Swarm deployment files are unchanged: the
release workflow rewrites the published `docker-compose.yml` for every release,
with a header naming it and the Hangar images pinned to its digests. Say
instead whether the deployment contract changes: the services, settings and
`variables.env` keys operators rely on.

Do not add generated commit lists, upstream SHAs, container digests, or verification
commands manually. The release workflow derives those from the signed tag, exact
upstream baseline, published Hangar releases, and GHCR manifests. Inherited Plane
tags are never eligible as the comparison baseline.

## Non-linear upstream transitions

Release-note generation normally requires the previous upstream revision to be
an ancestor of the current revision. This prevents an ambiguous comparison from
being presented as a complete upstream changelog after history is rewritten or a
release is rebuilt from another branch.

When maintainers have reviewed an intentional non-linear transition, add one
entry to `upstream-transition-reviews.json`. The entry must bind the current
Hangar release tag, previous published Hangar release tag, approved upstream
repository, exact previous and current upstream revisions, and a single-line
rationale. Treat that file as release authorization: review every field against
the signed tags and `UPSTREAM_BASE.json` history.

The generator still proves that both upstream revisions occur in the current
Hangar release history. It rejects missing, duplicate, malformed, stale, or
mismatched entries. For an accepted transition it links the two exact commits
separately; it does not generate a potentially misleading compare range.
