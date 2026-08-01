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
