## Security and privacy

**Creating a project failed, and the project was not created.** A new project is
given a random cover image bundled with the application, and a bundled cover is
copied into the workspace's storage rather than linked, because these are hashed
build assets whose filenames change with every release. That copy has to name the
record it belongs to — and it was being made before the project existed, with the
empty string as the identifier, which the API refuses. It could never have worked,
and because the cover is assigned by default, everyone who did not change the
image reached it.

Worse than the refusal was what followed it: the rejection happened before the
project was created at all, so a decorative image discarded the name, identifier,
lead and everything else the person had filled in. The copy now happens once the
project exists, using its real id, and a failure there costs the cover rather than
the project — it is reported as a warning and the project stands. The server's
refusal is correct and unchanged.

**God Mode stopped demanding a secret it will never show back.** Encrypted
configuration is write-only: the API returns an empty value for it and reports
separately whether one is stored, and it already treats an empty value on save as
"keep the existing secret". Both halves of the right behaviour were present. The
panel used neither, because the flag saying a secret exists appeared nowhere in
the console or its types, and the console flattens configuration to keys and
values, dropping it.

So the field rendered empty, was marked required, and blocked the form until the
operator fetched and retyped a credential the instance already held — in order to
change something else on the same page, such as the automatic Google redirect.
Five forms carried this: Google, GitHub, GitLab, Gitea and OIDC. The secret is now
required only while none is stored, so a provider still cannot be enabled without
one, and the field says so once one exists. Nothing changed about what the console
submits or about the API refusing to disclose a stored secret.

## Migrations and compatibility

No migrations. No configuration key is added, removed or reinterpreted, and no
stored value changes meaning.

**The checks that guard this repository now guard it.** Three of them looked like
gates and were not.

The API lint job ran ruff with `--fix`, which repairs what it finds and exits
zero, so the step reported success whatever it found and the repair went away with
the runner. Its log said as much under a passing check: "Found 1 error (1 fixed, 0
remaining)". That single error — an unused import — is removed here, which was the
entire cost of making the gate real. Ruff's version was also unpinned in CI while
the requirements file pinned an older one, so continuous integration and anyone
running it locally were linting with different versions; the workflow now reads
the pin from the requirements file, and the pin moves to the current release.

Formatting is now checked as well, deliberately only for `plane/ext` — the fork's
own API code, already clean. Across the wider tree ruff would rewrite 48 files, 41
of which are inherited from Plane and mostly carry Plane's own formatting rather
than any drift introduced here; rewriting them would put a formatting conflict in
every future upstream merge and buy nothing.

Most consequentially, no Python check gated a merge. Twelve checks ran on a pull
request touching the API and the five required ones were all front-end or
copyright, so a change that broke 1464 API tests could be merged with the evidence
in plain sight. They could not simply be marked required: the path filter lived on
the workflow trigger, which stops the whole workflow from starting, and a required
check that never reports blocks a pull request forever. The filter now lives in a
job that asks which files changed, the heavy jobs are gated on its answer, and a
gate job runs unconditionally and treats a skipped job as success. Both behaviours
were verified against a deliberately failing test before the branch rules were
changed.

Five packages also carried unit tests that no workflow had ever run — they passed
once, when someone ran them by hand. They run on every pull request now, as do
source-level contract tests for the God Mode forms and the project-creation path.

The inherited Plane baseline remains final `v1.4.0` at commit `917b23a6`. The
qualification boundary remains Kubernetes 1.30 through 1.36 (including 1.36.2),
Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress with
WebSocket support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.35`, the chart version is `0.1.0-rc.35`, the
signed Git tag is `hangar-v0.1.0-rc.35`, and the OCI chart reference is
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.35`. `rc.34` is the immediately previous
complete publication. `rc.1`, `rc.2`, `rc.20`, `rc.24`, `rc.25`, `rc.28`, and
`rc.33` were consumed by incomplete publication attempts and are not upgrade or
rollback targets.

## Known limitations and rollback

Hangar `rc.35` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

Rolling back to `rc.34` is clean: nothing in this release changes the database or
the meaning of any stored value. It returns project creation to failing whenever
the cover image is left at its default, and returns the console to demanding a
stored OAuth secret before any other setting on the same page can be saved.

Two behaviours in this release have automated coverage but no manual verification
against a real deployment, and each should be exercised on a non-production
instance first: saving a provider's settings without touching its secret, then
confirming sign-in through that provider still works — which is the only proof the
stored secret was not cleared — and creating a project under an account that may
not set a project cover, which should now produce a project and a warning rather
than nothing at all.

Both defects fixed here were reachable in ordinary use and neither was caught
before release, which is the reason the release also carries the CI work above.
