## Security and privacy

`rc.12` synchronizes the inherited Plane source to `v1.4.0-rc2` and incorporates
several access-control corrections. Workspace-level cycle and module listings now
require membership in the selected project. Project-member permission reads and
page-version reads are scoped to the project in the request URL. Guest issue
listings are restricted to issues created by that guest.

Bulk asset association now requires the current user to be the uploader and
accepts only an unassigned asset or one already assigned to the target project.
This preserves the normal fresh-upload workflow while preventing cross-user and
cross-project asset reassignment. Uploaded filenames also have control characters
removed before storage.

The release upgrades `js-yaml` to 4.3.0 to address excessive CPU use from YAML
merge-key chains and `valibot` to 1.4.2 to prevent inherited object-property names
from breaking flattened validation paths. It also includes current security
updates for `mistune`, `postcss`, and `sharp`. This release adds no telemetry,
external destination, Secret exposure, public object-storage route, chart
permission, or network-policy exception.

## Migrations and compatibility

There is no new Django database migration and no Helm values or Kubernetes
resource contract change in `rc.12`. The inherited Plane source is
`v1.4.0-rc2`, whose root `package.json` reports version `1.4.0`. The updated
client and server code should be deployed together: roll out the API, workers,
Live service, frontends, and migration Job as one Helm release rather than
keeping mixed `rc.11` and `rc.12` application versions.

Kubernetes 1.30 through 1.36, Helm 4.2, `linux/amd64`, Restricted Pod Security
Admission, TLS ingress with WebSocket support, a `NetworkPolicy`-enforcing CNI,
and persistent storage remain the qualified boundary. Existing `rc.11` values
remain compatible, but operators should render and review them against the
`0.1.0-rc.12` chart before upgrading.

## Known limitations and rollback

The inherited Plane version is a release candidate, and Hangar `rc.12` remains a
prerelease qualified for evaluation rather than production. Published images are
AMD64-only. The access-control fixes narrow previously overbroad reads and asset
association; clients that depended on data outside the selected project or on
associating another user's asset will now receive a denial.

Because this release introduces no schema or data migration, an application-only
rollback to `rc.11` does not require a database restore solely because `rc.12`
was deployed. Replace all `rc.12` application components with the `rc.11` chart
and images as one coordinated revision. Restore the pre-upgrade database backup
when unrelated writes, data corruption, or the incident being handled requires
point-in-time recovery.
