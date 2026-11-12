## Security and privacy

No security or privacy changes identified. The frontend images of earlier
releases sent API requests on Compose, Swarm and all-in-one installs to the
chart's placeholder origin, `hangar.example.com`, as described below. That name
sits under `example.com`, which is reserved for documentation and cannot be
registered by anybody else, so those requests failed and reached no third party.

## Migrations and compatibility

**The web app, God Mode and Spaces work again on Compose, Swarm and all-in-one
installs.** The published `web`, `admin` and `space` images carried the Helm
chart's placeholder origin, `https://hangar.example.com`, compiled in, and only
the chart replaced it at runtime. Every other install sent its API calls there,
the browser refused them under the Content-Security-Policy, and the apps could
not load their data. The images now carry no origin: the frontends
call the address the page was opened from, unless a runtime `config.js` names
another one, as the Helm chart's does. Release builds now fail if any of the
three images contains the placeholder.

**The Compose and Swarm installers find and download the release again.** They
asked GitHub for the latest release, which never returns a pre-release, and
every Hangar release so far is one, so the installer stopped before it began.
They also downloaded the release files from `v0.1.0-…` while the tags are named
`hangar-v0.1.0-…`. The installers now take the newest `hangar-v…` tag from the
release list and download its files from that tag. A release saved with the
`hangar-` prefix is read as the same version.

**The beat container stops when it is asked to.** Its start script ran
`celery beat` as a child process, so the stop signal reached only the shell,
which as the container's first process ignores it. `podman stop` and
`docker stop` waited ten seconds and then killed the container, which a
systemd unit wrapping it reports as a failure; Kubernetes waited the whole
termination grace period on every rollout of `beat-worker`. In the all-in-one
image, stopping beat left it running in the background, so restarting it could
start a second scheduler. The script now hands its process to `celery beat`,
which stops cleanly within a second.

Public work item pages in Spaces ask the API for link-preview metadata while
they render on the server. Without a configured API origin they now skip that
request instead of sending it to the placeholder; the page renders as before.

Upgrade from `0.1.0-rc.71`. This release adds no database migration and changes
no configuration, Helm value or Secret; no operator action is required. Helm
installs already set the origin through `config.js` and behave as before.

Product version is `v0.1.0-rc.72`, Git tag `hangar-v0.1.0-rc.72`, Helm chart
version `0.1.0-rc.72`, and OCI chart
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.72`.

## Known limitations and rollback

The limitations described in `0.1.0-rc.71` are unchanged. While the beat
container is still waiting for the database and migrations at start-up, a stop
still waits for the runtime's timeout. The Spaces
link-preview metadata described above is still not fetched on installs whose
images carry no API origin; it was not fetched before either.

Rolling back to `0.1.0-rc.71` needs no schema change and brings back the
compiled-in placeholder origin, so Compose, Swarm and all-in-one installs stop
working again; Helm installs are not affected. It also brings back the slow,
forced stop of the beat container. Rolling back further, to
`0.1.0-rc.70`, needs no schema change either and brings back its Alpine
packages and Effect release, as the rc.71 notes describe.
