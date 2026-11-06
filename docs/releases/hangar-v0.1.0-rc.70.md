## Security and privacy

No security or privacy changes identified.

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
back for the people it affected. Rolling back further, to `0.1.0-rc.68`, needs
the rc.69 migration reversed first, as the rc.69 notes describe.
