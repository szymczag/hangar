/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Fragment, useId, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane internal packages
import { Badge } from "@makeplane/propel/components/badge";
import type { BadgeVariant } from "@makeplane/propel/components/badge";
import { Banner } from "@makeplane/propel/components/banner";
import { CheckboxField } from "@makeplane/propel/components/checkbox-field";
import { InputField } from "@makeplane/propel/components/input-field";
import { Select, SelectContent, SelectItem, SelectList, SelectTrigger } from "@makeplane/propel/components/select";
import { TextButton } from "@makeplane/propel/components/text-button";
import { Icon } from "@makeplane/propel/components/icon";
import { KeyOutline } from "@makeplane/propel/icons";
import { InstanceService } from "@plane/services";
import type { TInstanceUser, TInstanceUserSignInStatus } from "@plane/types";
import { Skeleton } from "@plane/blocks/skeleton";
import { cn } from "@plane/utils";
// components
import { PageWrapper } from "@/components/common/page-wrapper";
// local
import { OpenPGPPanel } from "./openpgp-control";
// types
import type { Route } from "./+types/page";

const instanceService = new InstanceService();

const STATUS_COPY: Record<TInstanceUserSignInStatus, { label: string; hint: string; variant: BadgeVariant }> = {
  federated: {
    label: "Federated",
    hint: "Signs in through an identity provider.",
    variant: "success",
  },
  adoptable: {
    label: "Adoptable",
    hint: "Has used this provider before; adopted automatically on the next sign-in.",
    variant: "info",
  },
  "needs-import": {
    label: "Needs import",
    hint: "Nothing links this account to the provider. Sign-in would be refused until its subject is imported.",
    variant: "warning",
  },
  "password-only": {
    label: "Password only",
    hint: "No identity provider linked.",
    variant: "neutral",
  },
};

const PROVIDER_CHECK_OPTIONS: Record<string, string> = {
  none: "No cutover check",
  google: "Check against Google",
  oidc: "Check against OIDC",
  saml: "Check against SAML",
};

function SignInRecords({ user }: { user: TInstanceUser }) {
  if (user.federated_identities.length > 0) {
    return (
      <div className="flex flex-col gap-0.5">
        {user.federated_identities.map((identity) => (
          <span key={`${identity.provider}-${identity.issuer}`} className="font-mono text-caption-md-regular">
            {identity.provider} · {identity.issuer}
          </span>
        ))}
      </div>
    );
  }
  if (user.oauth_accounts.length > 0) {
    return <span className="font-mono text-caption-md-regular">{user.oauth_accounts.join(", ")}</span>;
  }
  return <span className="text-tertiary">—</span>;
}

const InstanceUsersPage = observer(function InstanceUsersPage(_props: Route.ComponentProps) {
  const [search, setSearch] = useState("");
  const [provider, setProvider] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const providerLabelId = useId();
  // the account whose encryption-key panel is open, in a row of its own under it
  const [keyPanelUserId, setKeyPanelUserId] = useState<string | null>(null);
  const keyPanelId = useId();

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
      <div className="flex flex-wrap items-end gap-3 pb-4">
        <div className="w-64">
          <InputField
            size="md"
            orientation="vertical"
            label="Search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by email"
          />
        </div>
        <div className="flex flex-col gap-1">
          <span id={providerLabelId} className="text-body-xs-medium text-primary">
            Cutover check
          </span>
          <Select
            items={PROVIDER_CHECK_OPTIONS}
            value={provider || "none"}
            onValueChange={(value) => setProvider(value === "none" ? "" : (value as string))}
          >
            <SelectTrigger variant="secondary" size="md" width="fit" aria-labelledby={providerLabelId} />
            <SelectContent>
              <SelectList>
                {Object.entries(PROVIDER_CHECK_OPTIONS).map(([key, label]) => (
                  <SelectItem key={key} value={key} label={label} />
                ))}
              </SelectList>
            </SelectContent>
          </Select>
        </div>
        <div className="pb-1.5">
          <CheckboxField
            size="md"
            label="Include deactivated"
            checked={includeInactive}
            onCheckedChange={(checked) => setIncludeInactive(checked)}
          />
        </div>
      </div>

      {provider && needsImport > 0 && (
        <div className="mb-4">
          <Banner
            placement="inline"
            variant="warning"
            title={`${needsImport} account${needsImport === 1 ? "" : "s"} would be refused`}
            description={
              <>
                if you pinned their domain to {provider}. Import each one&apos;s subject with{" "}
                <span className="font-mono">import_federated_identities</span> before setting{" "}
                <span className="font-mono">SSO_ENFORCED_DOMAINS</span>.
              </>
            }
          />
        </div>
      )}

      {isLoading ? (
        <Skeleton className="space-y-4">
          <Skeleton.Item height="40px" />
          <Skeleton.Item height="40px" />
          <Skeleton.Item height="40px" />
        </Skeleton>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-body-xs-regular">
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
                const isKeyPanelOpen = keyPanelUserId === user.id;
                return (
                  <Fragment key={user.id}>
                    <tr className={cn("align-top", !isKeyPanelOpen && "border-b border-subtle/60")}>
                      <td className="py-2 pr-4">
                        <div className={cn(!user.is_active && "text-tertiary line-through")}>{user.email}</div>
                        {!user.is_active && <div className="text-caption-md-regular text-tertiary">deactivated</div>}
                      </td>
                      <td className="py-2 pr-4">
                        <Badge variant={copy.variant} size="sm" label={copy.label} title={copy.hint} />
                      </td>
                      <td className="py-2 pr-4">{user.has_password ? "yes" : "no"}</td>
                      <td className="py-2 pr-4">
                        <SignInRecords user={user} />
                      </td>
                      <td className="py-2 pr-4">
                        <TextButton
                          variant="primary"
                          size="md"
                          icon={<Icon icon={KeyOutline} />}
                          aria-expanded={isKeyPanelOpen}
                          aria-controls={isKeyPanelOpen ? `${keyPanelId}-${user.id}` : undefined}
                          onClick={() => setKeyPanelUserId(isKeyPanelOpen ? null : user.id)}
                          label="Manage key"
                        />
                      </td>
                    </tr>
                    {isKeyPanelOpen && (
                      <tr id={`${keyPanelId}-${user.id}`} className="border-b border-subtle/60">
                        <td colSpan={5} className="pb-4">
                          <OpenPGPPanel userId={user.id} email={user.email} onClose={() => setKeyPanelUserId(null)} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
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
