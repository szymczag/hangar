/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Reading and writing the three domain-policy settings as rows.
 *
 * The stored format is the server's, unchanged: `corp.com=google`,
 * `corp.com=slug:member` and `corp.com=slug/IDENT:member`. What changes is that
 * an operator no longer composes those strings by hand across three fields,
 * keeping the domain spelled identically in each and remembering which
 * separator means what. A typo there produces no error — the entry is dropped
 * so that one mistake cannot stop the rest of a directory from signing in —
 * and the policy silently does not apply.
 *
 * Two rules of the stored format are easy to get wrong and are enforced here:
 * roles are written by name, because the server refuses an entry whose role it
 * does not recognise; and a domain may map to several workspaces, so reading
 * must not collapse them or saving would delete the ones not shown.
 */

export const FEDERATED_PROVIDERS = ["google", "oidc", "saml"] as const;
export const OTHER_PROVIDERS = ["github", "gitlab", "gitea"] as const;
export const ALL_PROVIDERS = [...FEDERATED_PROVIDERS, ...OTHER_PROVIDERS] as const;

export type TProvider = (typeof ALL_PROVIDERS)[number];

/** The names the server accepts, and the numbers it stores them as. */
export const ROLE_NAMES = ["guest", "member", "admin"] as const;
export type TRoleName = (typeof ROLE_NAMES)[number];
const ROLE_NUMBERS: Record<TRoleName, string> = { guest: "5", member: "15", admin: "20" };

export type TWorkspaceGrant = {
  /** Client-side only, so removing a grant does not remount the others. */
  id: string;
  workspaceSlug: string;
  workspaceRole: TRoleName;
  projectIdentifier: string;
  projectRole: TRoleName;
};

export type TDomainRow = {
  id: string;
  domain: string;
  /** Empty means "any federated provider", which is what a bare domain stores. */
  providers: TProvider[];
  grants: TWorkspaceGrant[];
};

let counter = 0;

function nextId(): string {
  counter += 1;
  return `row-${counter}`;
}

export function emptyGrant(): TWorkspaceGrant {
  return {
    id: nextId(),
    workspaceSlug: "",
    workspaceRole: "guest",
    projectIdentifier: "",
    projectRole: "guest",
  };
}

export function emptyRow(): TDomainRow {
  return { id: nextId(), domain: "", providers: [], grants: [] };
}

/**
 * Accept a role written either way.
 *
 * The server takes names; this panel wrote numbers for one release, and those
 * entries were discarded on read. Reading both means an instance configured by
 * that version shows what it actually has rather than defaulting to guest —
 * which would then be written back, quietly lowering the role.
 */
function roleFrom(value: string | undefined): TRoleName {
  const candidate = (value ?? "").trim().toLowerCase();
  if ((ROLE_NAMES as readonly string[]).includes(candidate)) return candidate as TRoleName;
  const byNumber = (Object.keys(ROLE_NUMBERS) as TRoleName[]).find((name) => ROLE_NUMBERS[name] === candidate);
  return byNumber ?? "guest";
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
    const key = domain.trim().toLowerCase();
    if (!rows.has(key)) rows.set(key, { ...emptyRow(), domain: key });
    return rows.get(key) as TDomainRow;
  };

  for (const entry of splitEntries(enforced)) {
    const [domain, providers] = entry.split("=");
    if (!domain?.trim()) continue;
    const row = rowFor(domain);
    row.providers = (providers ?? "")
      .split(";")
      .map((value) => value.trim().toLowerCase())
      .filter((value): value is TProvider => (ALL_PROVIDERS as readonly string[]).includes(value));
  }

  for (const entry of splitEntries(workspaces)) {
    const [domain, target] = entry.split("=");
    if (!domain?.trim() || !target) continue;
    const [slug, role] = target.split(":");
    if (!slug?.trim()) continue;
    // Appended, not assigned: the server accumulates several workspaces per
    // domain, so overwriting here would delete the rest on the next save.
    rowFor(domain).grants.push({
      ...emptyGrant(),
      workspaceSlug: slug.trim(),
      workspaceRole: roleFrom(role),
    });
  }

  for (const entry of splitEntries(projects)) {
    const [domain, target] = entry.split("=");
    if (!domain?.trim() || !target) continue;
    const [path, role] = target.split(":");
    const [slug, identifier] = (path ?? "").split("/");
    if (!slug?.trim() || !identifier?.trim()) continue;
    const row = rowFor(domain);
    const grant = row.grants.find((candidate) => candidate.workspaceSlug === slug.trim());
    if (grant) {
      grant.projectIdentifier = identifier.trim();
      grant.projectRole = roleFrom(role);
      continue;
    }
    // A project entry without its workspace entry is a configuration the server
    // skips. It is shown rather than hidden, and filling in the workspace here
    // would report a seat the instance does not actually grant.
    row.grants.push({
      ...emptyGrant(),
      projectIdentifier: identifier.trim(),
      projectRole: roleFrom(role),
    });
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

    for (const grant of row.grants) {
      const slug = grant.workspaceSlug.trim();
      if (!slug) continue;

      // By name. The server refuses an entry whose role it does not recognise,
      // and until this was fixed it did not recognise the numbers.
      workspaces.push(`${domain}=${slug}:${grant.workspaceRole}`);

      // A project seat without a workspace seat is a state the rest of the
      // product does not expect, so the project entry only exists alongside one.
      if (grant.projectIdentifier.trim()) {
        projects.push(`${domain}=${slug}/${grant.projectIdentifier.trim().toUpperCase()}:${grant.projectRole}`);
      }
    }
  }

  return {
    SSO_ENFORCED_DOMAINS: enforced.join(","),
    SSO_AUTO_JOIN_WORKSPACES: workspaces.join(","),
    SSO_AUTO_JOIN_PROJECTS: projects.join(","),
  };
}
