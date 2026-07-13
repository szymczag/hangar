## Security and privacy

`rc.5` replaces password composition rules with a minimum of 15 Unicode code
points and guessability-based validation. The browser meter and server-side
password setters now use zxcvbn dictionaries to reject common, predictable, and
context-derived passwords without requiring digits, symbols, or mixed case.

The frontend loads its canonical public origin from a no-store runtime
configuration file, the backend trusts only the deployment's forwarded host,
port, and TLS scheme settings, and bundled NGINX servers no longer disclose
internal listener ports in redirects.

## Migrations and compatibility

There is no database migration. New and reset passwords must satisfy the new
15-character and guessability policy; existing password hashes remain valid.

The chart gains optional Gateway API resources for Envoy-style deployments. Set
`gateway.enabled=true`, configure an existing Gateway parent or let the chart
create one, and leave the NGINX Ingress disabled. The chart renders explicit
routes for `/god-mode`, `/spaces`, `/live`, `/api`, and `/`, and normalizes the
four application prefixes with relative-host 308 redirects. Existing Ingress
deployments remain supported.

## Known limitations and rollback

The chart's runtime `config.js` supplies deployment-specific Vite URLs for Helm
installs. Other packaging must either serve an equivalent file or build the
static frontend images with all five `VITE_*_BASE_URL` variables set to the
external origin.

Gateway API redirect and request-header filters require a controller that
implements the corresponding HTTPRoute features. Rolling back restores the old
password and routing behavior; it does not invalidate passwords created under
`rc.5` or reverse external Gateway resources managed outside the release.
