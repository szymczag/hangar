## Security and privacy

**Google Calendar consent accepts Google's canonical email scope.** Hangar asks
for the OIDC `email` scope, but Google's token endpoint may report the same grant
as `https://www.googleapis.com/auth/userinfo.email`. The callback previously
compared those strings literally and rejected valid consent as `missing_scopes`.
It now treats the two spellings as aliases while continuing to require
`openid`, calendar read-only access, and free/busy access independently.

**OAuth callback failures expose only fixed diagnostic codes to logs.** The
calendar callback records allow-listed failure identifiers such as
`missing_scopes` and `invalid_token_response`. It does not log the authorization
code, access or refresh tokens, token response, exception contents, or values
derived from the OAuth request.

**The proxy build is reproducible against immutable Caddy base images.** Both
the builder and runtime use Caddy 2.11.4 images pinned to Linux AMD64 manifest
digests. Docker Hub references are fully qualified for Docker and Podman
portability, and the explicit gRPC module version matches the Caddy patch
release. A repository contract test rejects floating or mismatched base-image
versions.

## Migrations and compatibility

There is no database migration and no change to Helm values, Secrets, storage,
RBAC, NetworkPolicies, public routes, or the inherited Plane baseline. Existing
`rc.45` deployment configuration remains compatible.

The OAuth change affects only validation of the scope string returned by Google.
Existing connected credentials remain valid and need no migration. Operators do
not need to change the Google Cloud OAuth consent screen or redirect URI.

The proxy still publishes for AMD64 and keeps the existing Caddyfile and module
set; only the Caddy patch release, immutable base-image selection, and aligned
gRPC dependency change. Deploy all release images together as the normal release
unit.

## Known limitations and rollback

The calendar correction is covered by unit and callback contract tests for both
email-scope spellings, missing scopes, malformed token responses, and secret-free
logging. It has not been exercised against a live Google account as part of
release preparation.

The Caddy module set compiled successfully locally, and CI verifies the pinned
base-image contract. No new live-cluster qualification was performed because the
chart contract and workload topology did not change. The evaluation profile
remains qualified on AMD64 only; the production profile remains unsupported.

Rolling back to `rc.45` requires no schema reversal or configuration change. It
restores the callback bug for Google responses that canonicalize `email` and the
older floating Caddy base-image references, so prefer a forward correction if
this release needs replacement.
