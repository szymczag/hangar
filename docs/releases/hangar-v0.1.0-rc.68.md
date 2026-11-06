## Security and privacy

**No change in this release alters what is read, written, stored or shown.**
It repairs the upgrade path into `0.1.0-rc.64` and later, and moves one
development tool past an advisory.

zod moves past its last open advisory. GHSA-mrhx-c7xc-m3w5 (unbounded
memory while validating oversized constrained collections) affects every zod
before 4.6.6. The only 3.x copy came in through `eslint-plugin-react-hooks`, a
development tool, and now resolves to 4.6.7, the version the application
already ships. The lockfile carries a single zod.

The Tiptap 2 `mergeAttributes` advisory listed as open in rc.67 does not apply:
the published `@tiptap/core` 2.27.3 already defines `__proto__` as a data
property there, which is the fix, and the advisory's version range is wrong for
that release.

## Migrations and compatibility

Upgrade from `0.1.0-rc.67`, or from `0.1.0-rc.63` or later directly. This
release carries **no new database migration**. It repairs one that shipped in
`0.1.0-rc.64`.

**Upgrading a database that holds a Workshop no longer fails.** The
migration that withdraws the Workshop type from projects that never used it
asked the historical `Issue` model for `objects`, a manager that model does not
carry: `Issue` declares `issue_objects`, which makes it the default, and a
migration sees only the default manager. Every installation with at least one
project offering Workshops stopped at that migration with
`AttributeError: type object 'Issue' has no attribute 'objects'`, and the
release Job failed. The tests migrated an empty database, where the loop never
ran, and the migration's own test used the live models, where `objects` exists.
The migration now queries through the base manager every historical model has,
and a new test runs it against the historical models with a Workshop present.

The migration is atomic, so an installation that failed there is still at
`ext.0036` and needs nothing but this release: the release Job applies `0037`,
`0038`, `0039` and `db.0134` as described for rc.64 and rc.65. An installation
that did pass `0037` held no Workshop link, so nothing ran for it then and
nothing changes for it now.

Product version is `v0.1.0-rc.68`, Git tag `hangar-v0.1.0-rc.68`, Helm chart
version `0.1.0-rc.68`, and OCI chart
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.68`.

## Known limitations and rollback

The limitations described in `0.1.0-rc.67` are unchanged, apart from the Tiptap
advisory described above.

`0.1.0-rc.64` through `0.1.0-rc.67` are not upgrade targets for an installation
that holds a Workshop; upgrade to this release instead. Rolling back to rc.67
needs no schema change and leaves the migration fixed in the database, since it
has already run; only a fresh upgrade through rc.67 would fail again.
