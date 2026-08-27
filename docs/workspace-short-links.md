# Default workspace short links

Hangar can give one workspace compact work-item addresses such as `/i/AA-123`.
Choose that workspace in **God Mode → Workspaces**. Select **Short links enabled**
again to clear the choice. This setting is instance-wide and is available only
when configuration is database-managed.

The stored value is the workspace UUID, not its slug. Renaming the workspace
therefore does not break compact links. The public instance configuration only
reports the UUID while that workspace still exists; a missing or invalid value
disables compact routing safely.

Only canonical work-item browse routes are shortened:

- `/workspace-name/browse/AA-123` becomes `/i/AA-123` for the selected workspace.
- Project, settings, archive, and all non-selected workspace routes keep their
  workspace slug.

The web compatibility layer resolves `/i/:workItem` to the selected workspace
for the existing authenticated layouts, stores, and authorization wrappers. It
also normalizes links and imperative navigation, and replaces an old canonical
browse URL after configuration loads. The visible URL remains compact; this is
not an HTTP redirect to the workspace-qualified address.

If the setting is absent, stale, or points to a workspace the signed-in user
cannot access, the existing authorization flow refuses the request without
revealing workspace contents.
