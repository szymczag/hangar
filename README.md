<p align="center">
  <img src="./hangar-logo.png" alt="Hangar" width="720" />
</p>

<p align="center">
  <a href="https://github.com/szymczag/hangar/actions/workflows/pull-request-build-lint-web-apps.yml"><img src="https://github.com/szymczag/hangar/actions/workflows/pull-request-build-lint-web-apps.yml/badge.svg?branch=preview&amp;event=push" alt="Web checks" /></a>
  <a href="https://github.com/szymczag/hangar/actions/workflows/api-tests.yml"><img src="https://github.com/szymczag/hangar/actions/workflows/api-tests.yml/badge.svg?branch=preview" alt="API tests" /></a>
  <a href="./LICENSE.txt"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue.svg" alt="License: AGPL-3.0" /></a>
  <a href="https://github.com/szymczag/hangar/issues"><img src="https://img.shields.io/badge/contributions-welcome-brightgreen.svg" alt="Contributions welcome" /></a>
</p>

# Hangar

Open-source project management for self-hosted teams.

Hangar is an independent, community-maintained fork of
[Plane](https://github.com/makeplane/plane), focused on extending the open-source
project-management core while keeping upstream updates practical.

> [!IMPORTANT]
> Hangar is under active development. It does not currently publish stable releases,
> hosted services, or production-ready container images. The `preview` branch is the
> integration branch for contributors.

Hangar is not affiliated with, endorsed by, or supported by Plane Software, Inc.
“Plane” and the Plane logo are trademarks of Plane Software, Inc.

## Project status

| Capability                                    | Status                              | Tracking                                              |
| --------------------------------------------- | ----------------------------------- | ----------------------------------------------------- |
| Fork maintenance guide and CI baseline        | Available on `preview`              | [FORK.md](FORK.md)                                    |
| Isolated backend extension scaffold           | Available on `preview`              | [#2](https://github.com/szymczag/hangar/pull/2)       |
| OIDC backend                                  | Available on `preview`              | [#3](https://github.com/szymczag/hangar/pull/3)       |
| OIDC administration and sign-in UI            | Available on `preview`              | [#4](https://github.com/szymczag/hangar/pull/4)       |
| SAML 2.0 backend                              | Available on `preview`              | [#5](https://github.com/szymczag/hangar/pull/5)       |
| SAML 2.0 administration and sign-in UI        | Available on `preview`              | [#6](https://github.com/szymczag/hangar/pull/6)       |
| Immutable federated SSO identity binding      | Available on `preview`              | [#45](https://github.com/szymczag/hangar/pull/45)     |
| Epics as level-1 work items                   | Available on `preview`              | [Feature guide](docs/epics-as-work-items.md)          |
| Legacy Epic API compatibility                 | Available on `preview`              | [Feature guide](docs/epics-as-work-items.md)          |
| Custom work-item types and properties backend | Available on `preview`              | [#10](https://github.com/szymczag/hangar/pull/10)     |
| Custom work-item types and properties UI      | Available on `preview`              | [#11](https://github.com/szymczag/hangar/pull/11)     |
| Time tracking and worklogs backend            | Available on `preview`              | [#12](https://github.com/szymczag/hangar/pull/12)     |
| Time tracking and worklogs UI                 | Available on `preview`              | [#13](https://github.com/szymczag/hangar/pull/13)     |
| Runner installation control-plane foundation  | Available on `preview`              | [#46](https://github.com/szymczag/hangar/pull/46)     |
| Secure SES delivery and optional OpenPGP      | Available on `preview`              | [#44](https://github.com/szymczag/hangar/pull/44)     |
| Todoist CSV importer                          | Available; opt-in and quota-bounded | [#50](https://github.com/szymczag/hangar/pull/50)     |
| Helm chart evaluation profile                 | Public prerelease                   | [Kubernetes documentation](docs/kubernetes/README.md) |

“In review” means the code is not yet part of the supported `preview` branch. Do not
plan a deployment around those capabilities until their pull requests have merged and
the table marks them as available.

## Deployment

- [Docker deployment](deployments/cli/community/README.md)
- [Kubernetes and Helm](docs/kubernetes/README.md) — `0.1.0-rc.11`
  evaluation release; production support gates remain open.
- [Amazon SES, deliverability, and OpenPGP email](docs/aws-ses-email-operations.md)
  — secure transactional-email configuration and operations.

## Feature and security documentation

- [Epics as work items](docs/epics-as-work-items.md) — enable the canonical Task
  and Epic types, create and filter Epics in Work Items, understand hierarchy
  invariants, and migrate from the former dedicated Epic surface.
- [Hangar Runner architecture and implementation plan](docs/hangar-runner-architecture.md)
  — implemented installation controls, security boundaries, and the execution
  work that remains unsupported.
- [Federated SSO security and migration](docs/federated-sso-security.md) — configure
  Google, OIDC, and SAML identity binding; migrate existing users; and verify a
  rollout without email-based account takeover.
- [Email delivery and OpenPGP](docs/email-delivery-and-openpgp.md) — user-facing
  behavior, data handling, threat boundaries, and verification guidance.
- [Email delivery technical reference](docs/email-technical-implementation-plan.md)
  — maintainer architecture, invariants, retention, and release evidence.
- [Importing from Todoist](docs/importing-from-todoist.md) — administrator workflow,
  CSV validation behavior, private source-file handling, durable dispatch,
  fenced per-row authorization, database idempotency, immutable retry/audit
  history, recovery, and troubleshooting. The importer is disabled by default
  and remains hidden until the operator opts in. Execute traffic uses a
  dedicated queue, while PostgreSQL admission budgets and per-user/workspace
  throttles bound concurrent work, retained source bytes, and rolling row use.
  The request throttles use atomic Valkey/Redis counters across API replicas and
  fail closed before parsing an upload when that dependency is unavailable.

The inherited Plane Community chart is not a Hangar release and is not supported
for new Hangar installations.

## Product links and exact source

Hangar defaults its help, documentation, issue, private security, and source links
to this GitHub repository. Operators can override those destinations with the
documented `HANGAR_*_URL` settings. Release images embed their Git revision so the
instance API can identify the exact corresponding source.

If you are stuck, [open a GitHub issue](https://github.com/szymczag/hangar/issues).
Do not include credentials, private workspace data, or vulnerability details in a
public issue. Report vulnerabilities through
[GitHub private vulnerability reporting](SECURITY.md).

> [!NOTE]
> Hangar's OIDC backend requires TLS 1.3 for discovery, token, JWKS, and userinfo
> connections. Identity providers or reverse proxies limited to TLS 1.2 are not
> supported.

> Hangar requires an HTTPS SAML IdP single sign-on endpoint. Because SAML uses a
> browser redirect to the IdP, TLS protocol negotiation is controlled by the browser
> and IdP rather than by Hangar; configure the IdP or its reverse proxy to require TLS 1.3.

## Privacy by default

Hangar does not send telemetry or perform an external release check by default. A
fresh installation, and an existing installation upgraded through the privacy
migration, has telemetry disabled. There is no fallback to a Plane-controlled
collector, release API, or changelog.

Telemetry requires two deliberate operator actions:

1. Configure `OTLP_ENDPOINT` with the absolute URL of a collector you control.
2. Enable telemetry in the Hangar instance administration screen.

If either condition is absent, the scheduled metrics task exits without opening a
network connection. When enabled, the metrics include instance ID, instance name,
domain, version and setup state; workspace IDs and slugs; and aggregate user,
workspace, project, work-item, module, cycle, page, and membership counts. Review
that payload and your collector's retention policy before opting in.

The administration screen reports whether a valid collector is available, but does
not reveal or edit its URL. Configure the collector through deployment settings so
the outbound destination remains under operator control.

```env
# Optional. Leave empty to keep telemetry offline.
OTLP_ENDPOINT=
OTLP_METRICS_PROTOCOL=grpc

# Optional. Leave empty to disable release discovery.
# If enabled, this must be a credential-free HTTPS URL resolving only to public IPs.
HANGAR_RELEASE_CHECK_URL=https://api.github.com/repos/szymczag/hangar/releases/latest

# Optional link displayed by the instance UI. No default is provided.
INSTANCE_CHANGELOG_URL=https://github.com/szymczag/hangar/releases
```

The optional release request uses certificate-verified HTTPS, blocks private,
loopback, link-local, reserved, and metadata-service destinations, pins the
connection to the validated DNS result, ignores ambient proxies, refuses redirects,
and limits the response size. Failures leave the locally packaged version as the
source of truth and do not block startup.

The endpoint must return a published Hangar GitHub Release whose `tag_name` uses
the strict `hangar-vMAJOR.MINOR.PATCH` namespace (or an approved `alpha.N`,
`beta.N`, or `rc.N` suffix). Hangar removes only the `hangar-` Git namespace before
displaying the product version; inherited Plane `v*` tags and malformed versions
are rejected. Release-built API and Live images embed that same product version as
`APP_VERSION`, so offline version reporting does not depend on the upstream
`package.json` value.

## Verifying release images

Approved semver-tagged container releases are signed by the Hangar publication
workflow using Cosign keyless signing and GitHub's OpenID Connect identity. The
signature is attached to the immutable image digest in GHCR and recorded in the
Sigstore transparency log. Manually dispatched `preview-*` images are intentionally
unsigned; a signature therefore identifies an image produced through the approved
release flow.

Install Cosign, obtain the digest for the version you intend to deploy, and verify
both the exact workflow identity and GitHub's OIDC issuer:

```sh
VERSION=v0.1.0-rc.11
GIT_TAG=hangar-$VERSION
DIGEST=sha256:replace-with-the-published-digest
IMAGE=ghcr.io/szymczag/hangar-api

cosign verify \
  --certificate-identity "https://github.com/szymczag/hangar/.github/workflows/build-branch.yml@refs/tags/${GIT_TAG}" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  "${IMAGE}@${DIGEST}"
```

Replace `api` with `web`, `admin`, `space`, `live`, `proxy`, or `aio` as needed.
Pin deployments to the verified digest rather than relying on the mutable `stable`
tag. Hangar also publishes an SBOM and GitHub build-provenance attestation for every
container image.

## Development quick start

### Requirements

- Docker Engine with Docker Compose
- Node.js 22.18 or newer
- Corepack (the repository pins its pnpm version)
- At least 12 GB of RAM recommended for the complete local stack

Clone the fork and prepare the local environment:

```sh
git clone https://github.com/szymczag/hangar.git
cd hangar
./setup.sh
```

Start the local infrastructure, then the application development servers:

```sh
docker compose -f docker-compose-local.yml up -d
pnpm dev
```

The web application runs at <http://localhost:3000>; instance administration runs at
<http://localhost:3001/god-mode/>.

For repository commands, testing expectations, and contribution workflow, see
[CONTRIBUTING.md](CONTRIBUTING.md). This quick start is for development, not a
production deployment guide.

## Fork architecture and upstream relationship

Fork-owned backend code is isolated in `apps/api/plane/ext/`, while frontend extensions
use the existing community-edition overlay and extension points. Necessary changes to
upstream-owned files are deliberately small and tracked in a core-touch ledger.

[FORK.md](FORK.md) explains the architecture, upstream synchronization workflow,
copyright-header policy, and complete core-touch ledger. Hangar follows Plane’s
`preview` branch using merge-based synchronization; it does not rewrite published fork
history.

For Plane itself, its hosted service, or upstream documentation, visit the
[Plane repository](https://github.com/makeplane/plane). Issues caused by Hangar should
be reported to Hangar rather than Plane.

## Participate

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull request.
- Report bugs and propose features in [Hangar Issues](https://github.com/szymczag/hangar/issues).
- Report vulnerabilities privately according to [SECURITY.md](SECURITY.md).
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md) in project spaces.

## License and attribution

Hangar is licensed under the [GNU Affero General Public License v3.0](LICENSE.txt).
It is derived from [Plane](https://github.com/makeplane/plane) and retains upstream
copyright and license notices. Hangar-specific changes are maintained by Maciej
Szymczak and contributors.
