<p align="center">
  <img src="./hangar-logo.png" alt="Hangar" width="720" />
</p>

<p align="center">
  <a href="https://github.com/szymczag/hangar/actions/workflows/pull-request-build-lint-web-apps.yml"><img src="https://github.com/szymczag/hangar/actions/workflows/pull-request-build-lint-web-apps.yml/badge.svg?branch=preview" alt="Web checks" /></a>
  <a href="https://github.com/szymczag/hangar/actions/workflows/api-tests.yml"><img src="https://github.com/szymczag/hangar/actions/workflows/api-tests.yml/badge.svg?branch=preview" alt="API tests" /></a>
  <a href="./LICENSE.txt"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue.svg" alt="License: AGPL-3.0" /></a>
  <a href="https://github.com/szymczag/hangar/issues"><img src="https://img.shields.io/badge/contributions-welcome-brightgreen.svg" alt="Contributions welcome" /></a>
</p>

# Hangar

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

| Capability                                    | Status                 | Tracking                                              |
| --------------------------------------------- | ---------------------- | ----------------------------------------------------- |
| Fork maintenance guide and CI baseline        | Available on `preview` | [FORK.md](FORK.md)                                    |
| Isolated backend extension scaffold           | Available on `preview` | [#2](https://github.com/szymczag/hangar/pull/2)       |
| OIDC backend                                  | Available on `preview` | [#3](https://github.com/szymczag/hangar/pull/3)       |
| OIDC administration and sign-in UI            | Available on `preview` | [#4](https://github.com/szymczag/hangar/pull/4)       |
| SAML 2.0 backend                              | Available on `preview` | [#5](https://github.com/szymczag/hangar/pull/5)       |
| SAML 2.0 administration and sign-in UI        | Available on `preview` | [#6](https://github.com/szymczag/hangar/pull/6)       |
| Epics backend                                 | Available on `preview` | [#7](https://github.com/szymczag/hangar/pull/7)       |
| Epics UI and required API surfaces            | Available on `preview` | [#9](https://github.com/szymczag/hangar/pull/9)       |
| Custom work-item types and properties backend | Available on `preview` | [#10](https://github.com/szymczag/hangar/pull/10)     |
| Custom work-item types and properties UI      | Available on `preview` | [#11](https://github.com/szymczag/hangar/pull/11)     |
| Time tracking and worklogs backend            | Available on `preview` | [#12](https://github.com/szymczag/hangar/pull/12)     |
| Time tracking and worklogs UI                 | Available on `preview` | [#13](https://github.com/szymczag/hangar/pull/13)     |
| Helm chart evaluation profile                 | Public prerelease      | [Kubernetes documentation](docs/kubernetes/README.md) |

“In review” means the code is not yet part of the supported `preview` branch. Do not
plan a deployment around those capabilities until their pull requests have merged and
the table marks them as available.

## Deployment

- [Docker deployment](deployments/cli/community/README.md)
- [Kubernetes and Helm](docs/kubernetes/README.md) — `0.1.0-rc.4`
  evaluation release; production support gates remain open.

The inherited Plane Community chart is not a Hangar release and is not supported
for new Hangar installations.

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
VERSION=v0.1.0-rc.4
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
