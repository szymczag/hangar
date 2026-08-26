/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Reading and writing the three domain-policy settings as rows.
 *
 * The stored format is unchanged — the server still parses
 * `corp.com=google`, `corp.com=slug:20` and `corp.com=slug/IDENT:15`. What
 * changes is that an operator no longer has to compose those strings by hand
 * across three fields, keeping the domain spelled identically in each and
 * remembering which separator means what. A typo there produces no error: the
 * entry is dropped and the policy silently does not apply.
 */

export const FEDERATED_PROVIDERS = ["google", "oidc", "saml"] as const;
export const OTHER_PROVIDERS = ["github", "gitlab", "gitea"] as const;
export const ALL_PROVIDERS = [...FEDERATED_PROVIDERS, ...OTHER_PROVIDERS] as const;

export type TProvider = (typeof ALL_PROVIDERS)[number];

/** Roles as the server stores them. */
export const ROLE_VALUES = { guest: "5", member: "15", admin: "20" } as const;
export type TRoleName = keyof typeof ROLE_VALUES;

export type TDomainRow = {
  /** Client-side only, so removing a row does not remount the ones after it. */
  id: string;
  domain: string;
  /** Empty means "any federated provider", which is what a bare domain stores. */
  providers: TProvider[];
  workspaceSlug: string;
  workspaceRole: TRoleName;
  projectIdentifier: string;
  projectRole: TRoleName;
};

let rowCounter = 0;

function nextRowId(): string {
  rowCounter += 1;
  return `row-${rowCounter}`;
}

export function emptyRow(): TDomainRow {
  return {
    id: nextRowId(),
    domain: "",
    providers: [],
    workspaceSlug: "",
    workspaceRole: "guest",
    projectIdentifier: "",
    projectRole: "guest",
  };
}

function roleFromValue(value: string | undefined): TRoleName {
  const found = (Object.keys(ROLE_VALUES) as TRoleName[]).find((name) => ROLE_VALUES[name] === (value ?? "").trim());
  return found ?? "guest";
}

function splitEntries(raw: string): string[] {
  return raw
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

/** Build the row list from the three stored strings. */
export function parsePolicy(enforced: string, workspaces: string, projects: string): TDomainRow[] {
  const rows = new Map<string, TDomainRow>();

  const rowFor = (domain: string) => {
    const key = domain.toLowerCase();
    if (!rows.has(key)) rows.set(key, { ...emptyRow(), domain: key });
    return rows.get(key) as TDomainRow;
  };

  for (const entry of splitEntries(enforced)) {
    const [domain, providers] = entry.split("=");
    if (!domain?.trim()) continue;
    const row = rowFor(domain.trim());
    row.providers = (providers ?? "")
      .split(";")
      .map((value) => value.trim().toLowerCase())
      .filter((value): value is TProvider => (ALL_PROVIDERS as readonly string[]).includes(value));
  }

  for (const entry of splitEntries(workspaces)) {
    const [domain, target] = entry.split("=");
    if (!domain?.trim() || !target) continue;
    const [slug, role] = target.split(":");
    const row = rowFor(domain.trim());
    row.workspaceSlug = (slug ?? "").trim();
    row.workspaceRole = roleFromValue(role);
  }

  for (const entry of splitEntries(projects)) {
    const [domain, target] = entry.split("=");
    if (!domain?.trim() || !target) continue;
    const [path, role] = target.split(":");
    const [slug, identifier] = (path ?? "").split("/");
    const row = rowFor(domain.trim());
    if (!row.workspaceSlug) row.workspaceSlug = (slug ?? "").trim();
    row.projectIdentifier = (identifier ?? "").trim();
    row.projectRole = roleFromValue(role);
  }

  return Array.from(rows.values());
}

/** Render the rows back into the three stored strings. */
export function serializePolicy(rows: TDomainRow[]): {
  SSO_ENFORCED_DOMAINS: string;
  SSO_AUTO_JOIN_WORKSPACES: string;
  SSO_AUTO_JOIN_PROJECTS: string;
} {
  const enforced: string[] = [];
  const workspaces: string[] = [];
  const projects: string[] = [];

  for (const row of rows) {
    const domain = row.domain.trim().toLowerCase();
    if (!domain) continue;

    // A bare domain means "any federated provider" to the server, so an empty
    // selection is written as the domain alone rather than as an empty list —
    // which the server would read as "no provider at all" and refuse everyone.
    enforced.push(row.providers.length > 0 ? `${domain}=${row.providers.join(";")}` : domain);

    if (row.workspaceSlug.trim()) {
      workspaces.push(`${domain}=${row.workspaceSlug.trim()}:${ROLE_VALUES[row.workspaceRole]}`);

      // A project seat without a workspace seat is a state the rest of the
      // product does not expect, so the project entry only exists alongside one.
      if (row.projectIdentifier.trim()) {
        projects.push(
          `${domain}=${row.workspaceSlug.trim()}/${row.projectIdentifier.trim().toUpperCase()}:${
            ROLE_VALUES[row.projectRole]
          }`
        );
      }
    }
  }

  return {
    SSO_ENFORCED_DOMAINS: enforced.join(","),
    SSO_AUTO_JOIN_WORKSPACES: workspaces.join(","),
    SSO_AUTO_JOIN_PROJECTS: projects.join(","),
  };
}
