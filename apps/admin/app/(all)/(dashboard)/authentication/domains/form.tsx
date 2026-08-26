/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import Link from "next/link";
import { Plus, Trash2 } from "lucide-react";
// plane internal packages
import { Button, getButtonStyling } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IFormattedInstanceConfiguration } from "@plane/types";
// components
import { CodeBlock } from "@/components/common/code-block";
// helpers
import { configurationErrorMessage } from "@/helpers/configuration-error";
// hooks
import { useInstance, useWorkspace } from "@/hooks/store";
import { useConfigurationEditable } from "@/hooks/use-configuration-editable";
// local
import type { TDomainRow, TProvider, TRoleName } from "./policy";
import { ALL_PROVIDERS, emptyRow, parsePolicy, serializePolicy } from "./policy";

type Props = {
  config: IFormattedInstanceConfiguration;
};

const ROLE_LABELS: Record<TRoleName, string> = {
  guest: "Guest",
  member: "Member",
  admin: "Admin",
};

export const InstanceSSODomainPolicyForm = observer(function InstanceSSODomainPolicyForm(props: Props) {
  const { config } = props;
  // store hooks
  const { updateInstanceConfigurations } = useInstance();
  const { workspaces, fetchWorkspaces } = useWorkspace();
  const isConfigurationEditable = useConfigurationEditable();
  // states
  const [rows, setRows] = useState<TDomainRow[]>(() =>
    parsePolicy(
      config.SSO_ENFORCED_DOMAINS ?? "",
      config.SSO_AUTO_JOIN_WORKSPACES ?? "",
      config.SSO_AUTO_JOIN_PROJECTS ?? ""
    )
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  useSWR("INSTANCE_WORKSPACES", () => fetchWorkspaces());

  const workspaceOptions = useMemo(() => Object.values(workspaces ?? {}), [workspaces]);

  const update = (index: number, patch: Partial<TDomainRow>) => {
    setRows((previous) => previous.map((row, position) => (position === index ? { ...row, ...patch } : row)));
    setIsDirty(true);
  };

  const toggleProvider = (index: number, provider: TProvider) => {
    const current = rows[index]?.providers ?? [];
    update(index, {
      providers: current.includes(provider) ? current.filter((value) => value !== provider) : [...current, provider],
    });
  };

  const onSubmit = async () => {
    setIsSubmitting(true);
    try {
      await updateInstanceConfigurations(serializePolicy(rows));
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Done!",
        message: "Domain policy saved. Test a sign-in from a pinned domain now.",
      });
      setIsDirty(false);
    } catch (error) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: configurationErrorMessage(error) });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <p className="max-w-3xl text-13 text-tertiary">
        One row per email domain. A pinned domain accepts only the providers you tick — password sign-in and magic codes
        are refused for it, on both sign-up and sign-in, so nobody can claim a colleague&apos;s address through a weaker
        route. Matching is exact, so <CodeBlock darkerShade>sub.corp.com</CodeBlock> needs its own row.
      </p>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-13">
          <thead className="text-tertiary">
            <tr className="border-b border-subtle text-left">
              <th className="py-2 pr-4 font-medium">Email domain</th>
              <th className="py-2 pr-4 font-medium">May sign in with</th>
              <th className="py-2 pr-4 font-medium">Joins workspace</th>
              <th className="py-2 pr-4 font-medium">as</th>
              <th className="py-2 pr-4 font-medium">Project</th>
              <th className="py-2 pr-4 font-medium">as</th>
              <th className="py-2 font-medium" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.id} className="border-b border-subtle/60 align-top">
                <td className="py-2 pr-4">
                  <input
                    className="w-44 rounded-md border border-strong bg-surface-1 px-2 py-1"
                    placeholder="corp.com"
                    value={row.domain}
                    onChange={(event) => update(index, { domain: event.target.value })}
                    disabled={!isConfigurationEditable}
                  />
                </td>
                <td className="py-2 pr-4">
                  <div className="flex flex-wrap gap-x-3 gap-y-1">
                    {ALL_PROVIDERS.map((provider) => (
                      <label key={provider} className="flex items-center gap-1 text-11">
                        <input
                          type="checkbox"
                          checked={row.providers.includes(provider)}
                          onChange={() => toggleProvider(index, provider)}
                          disabled={!isConfigurationEditable}
                        />
                        {provider}
                      </label>
                    ))}
                  </div>
                  {row.providers.length === 0 && (
                    <span className="text-11 text-tertiary">None ticked — any of Google, OIDC or SAML.</span>
                  )}
                </td>
                <td className="py-2 pr-4">
                  <select
                    className="w-40 rounded-md border border-strong bg-surface-1 px-2 py-1"
                    value={row.workspaceSlug}
                    onChange={(event) => update(index, { workspaceSlug: event.target.value })}
                    disabled={!isConfigurationEditable}
                  >
                    <option value="">Invite by hand</option>
                    {workspaceOptions.map((workspace) => (
                      <option key={workspace.id} value={workspace.slug}>
                        {workspace.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="py-2 pr-4">
                  <select
                    className="w-28 rounded-md border border-strong bg-surface-1 px-2 py-1"
                    value={row.workspaceRole}
                    onChange={(event) => update(index, { workspaceRole: event.target.value as TRoleName })}
                    disabled={!isConfigurationEditable || !row.workspaceSlug}
                  >
                    {(Object.keys(ROLE_LABELS) as TRoleName[]).map((role) => (
                      <option key={role} value={role}>
                        {ROLE_LABELS[role]}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="py-2 pr-4">
                  <input
                    className="w-28 rounded-md border border-strong bg-surface-1 px-2 py-1 uppercase"
                    placeholder="PLAT"
                    value={row.projectIdentifier}
                    onChange={(event) => update(index, { projectIdentifier: event.target.value })}
                    disabled={!isConfigurationEditable || !row.workspaceSlug}
                  />
                </td>
                <td className="py-2 pr-4">
                  <select
                    className="w-28 rounded-md border border-strong bg-surface-1 px-2 py-1"
                    value={row.projectRole}
                    onChange={(event) => update(index, { projectRole: event.target.value as TRoleName })}
                    disabled={!isConfigurationEditable || !row.projectIdentifier}
                  >
                    {(Object.keys(ROLE_LABELS) as TRoleName[]).map((role) => (
                      <option key={role} value={role}>
                        {ROLE_LABELS[role]}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="py-2">
                  <button
                    type="button"
                    aria-label="Remove domain"
                    className="text-tertiary hover:text-danger-primary"
                    onClick={() => {
                      setRows((previous) => previous.filter((_, position) => position !== index));
                      setIsDirty(true);
                    }}
                    disabled={!isConfigurationEditable}
                  >
                    <Trash2 className="size-4" />
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="py-6 text-center text-tertiary">
                  No domain is pinned. Everyone signs in with whatever methods are enabled.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            setRows((previous) => [...previous, emptyRow()]);
            setIsDirty(true);
          }}
          disabled={!isConfigurationEditable}
        >
          <Plus className="size-4" /> Add a domain
        </Button>
      </div>

      <div className="flex flex-col gap-2 rounded-md border border-subtle p-4 text-11 text-tertiary">
        <span>
          <strong className="text-secondary">Project identifier</strong> is the short code on a project&apos;s work
          items, such as <CodeBlock darkerShade>PLAT-42</CodeBlock> → <CodeBlock darkerShade>PLAT</CodeBlock>. A project
          seat is only granted alongside a workspace seat, and archived projects are skipped.
        </span>
        <span>
          An existing membership is never modified, so a role you lowered by hand stays lowered. Joining happens on
          sign-in, and only for domains pinned here.
        </span>
        <span>
          Pinning removes password and magic-link sign-in for a domain. Import identities and confirm sign-in for a few
          accounts <strong className="text-secondary">before</strong> pinning, and read the break-glass guidance first.
        </span>
      </div>

      <div className="flex items-center gap-4">
        <Button
          variant="primary"
          size="lg"
          onClick={onSubmit}
          loading={isSubmitting}
          disabled={!isDirty || isSubmitting || !isConfigurationEditable}
        >
          {isSubmitting ? "Saving" : "Save changes"}
        </Button>
        <Link href="/authentication" className={getButtonStyling("secondary", "lg")}>
          Go back
        </Link>
      </div>
    </div>
  );
});
