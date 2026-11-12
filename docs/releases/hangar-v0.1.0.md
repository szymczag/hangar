## Security and privacy

No security or privacy changes identified. This release carries the code of
`0.1.0-rc.72` and changes only how the Compose and Swarm installers choose a
release.

## Migrations and compatibility

**Hangar 0.1.0 is the first stable release.** Every earlier version was
published as a release candidate. This one is published as a stable release, so
GitHub's `releases/latest` links resolve, and every image gains a `stable` tag
that points at `v0.1.0`. The stable release covers Docker Compose, Docker Swarm
and the all-in-one image. The Helm chart is published with it as version
`0.1.0`, but on Kubernetes the release remains qualified for evaluation only, as
the Kubernetes documentation describes.

**Stable installs stay on stable releases.** The Compose and Swarm installers
looked up the newest release, release candidate or not, which was right while
every release was a candidate. They now take the newest stable release, and the
newest release candidate only while no stable release has been published, so
`upgrade` does not move a stable install onto a later release candidate.

Upgrade from `0.1.0-rc.72`. This release adds no database migration and changes
no configuration, Helm value or Secret; no operator action is required. An
upgrade from an earlier release candidate also takes in the changes described
in the notes of each release in between.

Product version is `v0.1.0`, Git tag `hangar-v0.1.0`, Helm chart version
`0.1.0`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.1.0`.

## Known limitations and rollback

The limitations described in `0.1.0-rc.72` are unchanged. The Kubernetes
production profile has not completed qualification: production installs with
external services, backup and restore, migration-failure recovery and the
support matrix remain open, so do not run the chart in production yet. The
mutable `stable` tag moves with every later stable release; pin a deployment to
a version or digest to control when it changes.

Rolling back to `0.1.0-rc.72` needs no schema change and changes no
application behaviour; only the installers return to taking the newest release
of any kind. The `stable` tag is not moved back by a rollback.
