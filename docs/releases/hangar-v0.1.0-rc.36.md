## Security and privacy

**An account that signs in through an identity provider could change its own
email address.** Nothing checked for a federated identity before accepting the
change, so proving control of any other mailbox with a verification code was
enough.

The refusal this adds is not about sign-in. The federated binding is a digest
over provider, issuer, subject format and subject, and the email address takes no
part in it — a changed address would not have stopped the account signing in,
which is precisely why the change had to be refused rather than left to fail on
its own. The address is what policy reads: `SSO_ENFORCED_DOMAINS` pins a domain to
a provider, and auto-join grants workspaces by the domain of the address. An
account could therefore keep the identity that admitted it while moving out from
under the policy that governs it, or into one that would grant it more.

Both entry points are refused, because blocking only the change itself would
still have sent a verification code to the other mailbox first. Accounts that sign
in with a password are untouched and their addresses remain changeable.

Nothing in the logs would have distinguished this from ordinary use, and any
instance with `SSO_ENFORCED_DOMAINS` configured was exposed to it. Operators of
such an instance may wish to compare current addresses against the domains they
pinned.

## Migrations and compatibility

No migrations. No configuration key is added, removed or reinterpreted, and no
stored value changes meaning.

**Profile settings stopped offering what the provider owns.** Someone signed in
through a provider could edit their name, display name and picture; the edits took
effect and were reverted by the next sign-in with no explanation, because
attribute sync rewrites them. The picture was worse than reverted — sync deletes
an uploaded avatar from storage before writing the provider's, so the file was
lost rather than replaced, and both ways into that upload are now closed.

These fields are read-only only where sync is enabled for the provider the account
signs in through. An account federated with sync switched off still owns them,
which is a different question from whether the account is federated at all, and
the two are deliberately kept apart. The onboarding step had already answered the
first question and now shares that answer rather than deciding separately.

**API tokens are offered only where one can be created.** A token names the
workspace it acts in, and minting one requires a role there at or above
`API_TOKEN_MINIMUM_ROLE`. That was enforced correctly, but the settings page
showed the create button to everyone and the dialog listed every workspace the
account belonged to — so the label, description and expiry were filled in before
anything checked, and the refusal arrived on save.

The threshold is now reported to the application, which asks the same question
first: the workspace chooser lists the memberships that qualify, and where none do
the offer is withdrawn with the reason. Existing tokens stay listed and revocable
regardless, because raising the threshold governs minting rather than tokens
already issued. This is presentation and not a boundary — the endpoint still
decides, and decides the same way whatever the interface showed. The threshold is
read from one place precisely so the offer and the refusal cannot drift apart.








The inherited Plane baseline remains final `v1.4.0` at commit `917b23a6`. The
qualification boundary remains Kubernetes 1.30 through 1.36 (including 1.36.2),
Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress with
WebSocket support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.36`, the chart version is `0.1.0-rc.36`, the
signed Git tag is `hangar-v0.1.0-rc.36`, and the OCI chart reference is
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.36`. `rc.35` is the immediately previous
complete publication. `rc.1`, `rc.2`, `rc.20`, `rc.24`, `rc.25`, `rc.28`, and
`rc.33` were consumed by incomplete publication attempts and are not upgrade or
rollback targets.

## Known limitations and rollback

Hangar `rc.36` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

Rolling back to `rc.35` is clean in the sense that nothing here changes the
database, but it restores the email-change defect above. An instance relying on
`SSO_ENFORCED_DOMAINS` should treat `rc.35` and everything before it as affected
rather than as an equivalent fallback.

Three behaviours have automated coverage but no manual verification against a real
deployment, and each should be exercised on a non-production instance first:
attempting an email change while signed in through a provider, which should be
refused before any code is sent; opening profile settings on such an account,
where the name should be stated as managed by the provider; and opening the API
token page as an account holding only roles below the configured threshold, where
the create button should be absent while existing tokens remain revocable.
