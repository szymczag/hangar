/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane internal packages
import { InstanceService } from "@plane/services";
import type { TInstanceUser, TInstanceUserSignInStatus } from "@plane/types";
import { Loader } from "@plane/ui";
import { cn } from "@plane/utils";
// components
import { PageWrapper } from "@/components/common/page-wrapper";
// local
import { OpenPGPControl } from "./openpgp-control";
// types
import type { Route } from "./+types/page";

const instanceService = new InstanceService();

const STATUS_COPY: Record<TInstanceUserSignInStatus, { label: string; hint: string; tone: string }> = {
  federated: {
    label: "Federated",
    hint: "Signs in through an identity provider.",
    tone: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
  },
  adoptable: {
    label: "Adoptable",
    hint: "Has used this provider before; adopted automatically on the next sign-in.",
    tone: "bg-sky-500/10 text-sky-600 border-sky-500/30",
  },
  "needs-import": {
    label: "Needs import",
    hint: "Nothing links this account to the provider. Sign-in would be refused until its subject is imported.",
    tone: "bg-amber-500/10 text-amber-700 border-amber-500/30",
  },
  "password-only": {
    label: "Password only",
    hint: "No identity provider linked.",
    tone: "bg-layer-3 text-tertiary border-transparent",
  },
};

function SignInRecords({ user }: { user: TInstanceUser }) {
  if (user.federated_identities.length > 0) {
    return (
      <div className="flex flex-col gap-0.5">
        {user.federated_identities.map((identity) => (
          <span key={`${identity.provider}-${identity.issuer}`} className="font-mono text-11">
            {identity.provider} · {identity.issuer}
          </span>
        ))}
      </div>
    );
  }
  if (user.oauth_accounts.length > 0) {
    return <span className="font-mono text-11">{user.oauth_accounts.join(", ")}</span>;
  }
  return <span className="text-tertiary">—</span>;
}

const InstanceUsersPage = observer(function InstanceUsersPage(_props: Route.ComponentProps) {
  const [search, setSearch] = useState("");
  const [provider, setProvider] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);

  const { data, isLoading } = useSWR(["INSTANCE_USERS", search, provider, includeInactive], () =>
    instanceService.users({
      ...(search ? { search } : {}),
      ...(provider ? { provider } : {}),
      ...(includeInactive ? { include_inactive: true } : {}),
      per_page: 50,
    })
  );

  const users = data?.results ?? [];
  const needsImport = users.filter((user) => user.status === "needs-import").length;

  return (
    <PageWrapper
      header={{
        title: "Users on this instance",
        description: "Who has an account and how they sign in. Read-only — accounts are managed from their workspace.",
      }}
    >
      <div className="flex flex-wrap items-center gap-3 pb-4">
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by email"
          className="rounded-sm border border-strong bg-surface-1 px-3 py-1.5 text-13 outline-none"
        />
        <select
          value={provider}
          onChange={(event) => setProvider(event.target.value)}
          className="rounded-sm border border-strong bg-surface-1 px-3 py-1.5 text-13 outline-none"
        >
          <option value="">No cutover check</option>
          <option value="google">Check against Google</option>
          <option value="oidc">Check against OIDC</option>
          <option value="saml">Check against SAML</option>
        </select>
        <label className="flex items-center gap-2 text-13 text-tertiary">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(event) => setIncludeInactive(event.target.checked)}
          />
          Include deactivated
        </label>
      </div>

      {provider && needsImport > 0 && (
        <div className="border-amber-500/40 bg-amber-500/10 mb-4 rounded-sm border px-4 py-3 text-13 leading-5">
          <span className="font-medium">
            {needsImport} account{needsImport === 1 ? "" : "s"} would be refused
          </span>{" "}
          if you pinned their domain to {provider}. Import each one&apos;s subject with{" "}
          <span className="font-mono">import_federated_identities</span> before setting{" "}
          <span className="font-mono">SSO_ENFORCED_DOMAINS</span>.
        </div>
      )}

      {isLoading ? (
        <Loader className="space-y-4">
          <Loader.Item height="40px" />
          <Loader.Item height="40px" />
          <Loader.Item height="40px" />
        </Loader>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-13">
            <thead className="text-tertiary">
              <tr className="border-b border-subtle text-left">
                <th className="py-2 pr-4 font-medium">Email</th>
                <th className="py-2 pr-4 font-medium">Status</th>
                <th className="py-2 pr-4 font-medium">Password</th>
                <th className="py-2 pr-4 font-medium">Sign-in records</th>
                <th className="py-2 pr-4 font-medium">Encryption key</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const copy = STATUS_COPY[user.status];
                return (
                  <tr key={user.id} className="border-b border-subtle/60 align-top">
                    <td className="py-2 pr-4">
                      <div className={cn(!user.is_active && "text-tertiary line-through")}>{user.email}</div>
                      {!user.is_active && <div className="text-11 text-tertiary">deactivated</div>}
                    </td>
                    <td className="py-2 pr-4">
                      <span className={cn("rounded-sm border px-2 py-0.5 text-11", copy.tone)} title={copy.hint}>
                        {copy.label}
                      </span>
                    </td>
                    <td className="py-2 pr-4">{user.has_password ? "yes" : "no"}</td>
                    <td className="py-2 pr-4">
                      <SignInRecords user={user} />
                    </td>
                    <td className="py-2 pr-4">
                      <OpenPGPControl userId={user.id} email={user.email} />
                    </td>
                  </tr>
                );
              })}
              {users.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-tertiary">
                    No matching users.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </PageWrapper>
  );
});

export const meta: Route.MetaFunction = () => [{ title: "Users - God Mode" }];

export default InstanceUsersPage;
