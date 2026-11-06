## Security and privacy

**The proxy's Caddy no longer carries a known HTML parser flaw.** The image scan
of rc.69 found `golang.org/x/net` 0.60.0 in the Caddy binary of the `proxy`
image. Its HTML parser can be made to exhaust resources by crafted input
(CVE-2026-78661, rated high). The build now pins `golang.org/x/net` 0.62.0, which
fixes it, together with `golang.org/x/crypto` 0.58.0 and `golang.org/x/text`
0.43.0, which that release requires, and still checks all three in the binary it
produces. The Caddyfile and every proxy setting are unchanged.

## Migrations and compatibility

**Your work opens again for anyone assigned a work item without a state.** The
user stats grouped a person's assigned work items by the group of their state,
so a work item with no state came back as a group of its own whose name was
null. The state distribution chart on the profile overview could not label that
group, and the whole page failed with an error instead of rendering. The user
stats and the user's own workspace dashboard summary now leave work items
without a state out of the state distribution; they still count towards assigned work. The chart also
skips any group it does not recognise.

Upgrade from `0.1.0-rc.69`. This release adds no database migration and changes
no configuration, Helm value or Secret; no operator action is required. The one
change visible to API clients is that `state_distribution` in the user stats and
the user's workspace dashboard summary no longer contains a row whose `state_group` is null.

Product version is `v0.1.0-rc.70`, Git tag `hangar-v0.1.0-rc.70`, Helm chart
version `0.1.0-rc.70`, and OCI chart
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.70`.

## Known limitations and rollback

The limitations described in `0.1.0-rc.69` are unchanged. Rolling back to
`0.1.0-rc.69` needs no schema change and brings the failing profile overview
back for the people it affected, along with the earlier `golang.org/x/net` in
the proxy. Rolling back further, to `0.1.0-rc.68`, needs
the rc.69 migration reversed first, as the rc.69 notes describe.
