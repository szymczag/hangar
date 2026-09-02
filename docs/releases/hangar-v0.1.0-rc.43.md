## Security and privacy

**Google Calendar trainer capacity is off unless an operator turns it on, and
refuses to start half-configured.** The integration reads trainers' calendar
busy times to work out who is available, which is a real disclosure of where
people are and when. It is therefore gated on `ENABLE_GOOGLE_CALENDAR_CAPACITY`,
which defaults to `0` in the shipped deployment environment, and the application
refuses to boot if it is switched on without `CALENDAR_TOKEN_ENCRYPTION_KEYS`.
An instance that never enables it carries the new tables and nothing else.

**Calendar OAuth tokens are encrypted at rest with rotatable keys.** Tokens are
sealed with Fernet and stored beside the identifier of the key that sealed them,
so a compromised key can be retired without invalidating every stored token at
once: decryption tries the named key first and falls back to the rest, which is
what makes rotation possible without a flag day. The keys come from the
deployment environment and are never read back through the API.

**Every capacity action is recorded in an append-only audit trail.**
`CapacityAuditEvent` rows are written through a queryset that refuses updates and
deletes, so the record of who connected a calendar, who read availability and who
changed a trainer's schedule cannot be edited afterwards by the same people it
describes.

**The capacity endpoints are throttled per user and per workspace, atomically.**
Calendar reads reach a third party on the instance's behalf, so an unthrottled
caller could both exhaust the upstream quota for everyone and use the instance as
an amplifier. The throttle fails closed: if its backing store is unavailable the
request is refused rather than allowed through unmetered.

**Operator-authored branding text now has a length cap and character
validation.** `INSTANCE_SUPPORT_TEXT`, the sign-in headline and subheading, and
the organisation name had neither. The support text is the one that mattered
most, because it is rendered on the pages shown when the instance cannot be
reached — a bidirectional override there reorders the sentence telling somebody
how to get help, at the moment nothing else works, and escaping downstream cannot
help because the characters are not markup. All four are now held to the same
rule as the maintenance notice and project names: nothing in Unicode category
`Cc` or `Cf`, and a cap sized to what the field is for. Clearing a value still
means "use the built-in wording".

**Dependency updates.** `djangorestframework` 3.17.1 to 3.17.2 and
`sanitize-html` 2.17.5 to 2.17.7.

## Migrations and compatibility

Four migrations are added, all additive: `db.0131` adds a workshop type,
and `ext.0017`, `ext.0018` and `ext.0019` create the trainer capacity tables, the
audit event table and a schedule revision column. No existing table is rewritten.

The capacity feature is inert until `ENABLE_GOOGLE_CALENDAR_CAPACITY=1` and
`CALENDAR_TOKEN_ENCRYPTION_KEYS` are set. Both are new environment variables,
present and empty in the shipped deployment files and described in the
Kubernetes configuration documentation. Turning the feature on without the keys
is refused at start-up rather than at first use, so the failure is visible when
the deployment changes rather than when somebody first tries to use it.

Because the migrations only add, an older application version runs against this
schema unchanged and simply does not read the new tables.

## Known limitations and rollback

The trainer capacity feature has not been exercised against a live Google
Calendar in this release. Its unit tests pass and its endpoints are covered, but
the OAuth consent round trip, token refresh and the behaviour when Google returns
an error have not been driven end to end. Anyone enabling it should do so on a
non-critical workspace first.

The maintenance bar, the build identity dialog and the workspace home-defaults
settings page have still not been viewed in a browser. Their behaviour was
verified against the released images — migrations, the maintenance notice's
disclosure gate, route resolution and the favicon wiring — but their appearance
has not been checked.

Copying work items is not supported. Project duplication carries a project's
configuration and never its work items, so a copy contains no work items and
therefore no sub-items either.

To roll back, redeploy the previous image and leave the new tables in place. If
the capacity feature was enabled, unset `ENABLE_GOOGLE_CALENDAR_CAPACITY` as part
of the rollback so the older image is not asked to read tables it does not know.
