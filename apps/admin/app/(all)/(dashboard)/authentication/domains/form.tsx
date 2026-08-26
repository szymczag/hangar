/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import Link from "next/link";
import { Plus, Trash2 } from "lucide-react";
// plane internal packages
import { Button, getButtonStyling } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IFormattedInstanceConfiguration } from "@plane/types";
import { Loader } from "@plane/ui";
// components
import { CodeBlock } from "@/components/common/code-block";
// helpers
import { configurationErrorMessage } from "@/helpers/configuration-error";
// hooks
import { useInstance, useWorkspace } from "@/hooks/store";
import { useConfigurationEditable } from "@/hooks/use-configuration-editable";
// local
import type { TDomainRow, TProvider, TRoleName, TWorkspaceGrant } from "./policy";
import { ALL_PROVIDERS, ROLE_NAMES, emptyGrant, emptyRow, parsePolicy, serializePolicy } from "./policy";

type Props = {
  config: IFormattedInstanceConfiguration;
};

const ROLE_LABELS: Record<TRoleName, string> = { guest: "Guest", member: "Member", admin: "Admin" };

export const InstanceSSODomainPolicyForm = observer(function InstanceSSODomainPolicyForm(props: Props) {
  const { config } = props;
  // store hooks
  const { updateInstanceConfigurations } = useInstance();
  const { workspaces, paginationInfo, loader, fetchWorkspaces, fetchNextWorkspaces } = useWorkspace();
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

  // The endpoint pages ten at a time. A domain pointing at the eleventh
  // workspace would otherwise have no matching option, and a select whose value
  // matches nothing displays its first option — so the row would read "Invite by
  // hand" while holding a slug, and the operator could not correct it because
  // their workspace was not in the list.
  useEffect(() => {
    if (paginationInfo?.next_page_results && loader !== "pagination") void fetchNextWorkspaces();
  }, [paginationInfo?.next_page_results, loader, fetchNextWorkspaces]);

  const workspaceOptions = useMemo(() => Object.values(workspaces ?? {}), [workspaces]);
  const isLoadingWorkspaces = loader === "init-loader" || Boolean(paginationInfo?.next_page_results);

  const markDirty = () => setIsDirty(true);

  const updateRow = (rowId: string, patch: Partial<TDomainRow>) => {
    setRows((previous) => previous.map((row) => (row.id === rowId ? { ...row, ...patch } : row)));
    markDirty();
  };

  const updateGrant = (rowId: string, grantId: string, patch: Partial<TWorkspaceGrant>) => {
    setRows((previous) =>
      previous.map((row) =>
        row.id === rowId
          ? { ...row, grants: row.grants.map((grant) => (grant.id === grantId ? { ...grant, ...patch } : grant)) }
          : row
      )
    );
    markDirty();
  };

  const toggleProvider = (row: TDomainRow, provider: TProvider) =>
    updateRow(row.id, {
      providers: row.providers.includes(provider)
        ? row.providers.filter((value) => value !== provider)
        : [...row.providers, provider],
    });

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

  const renderGrant = (row: TDomainRow, grant: TWorkspaceGrant) => {
    // A slug that is not among the options would silently display as "Invite by
    // hand". Carrying it as its own option keeps what is stored visible.
    const isUnknownSlug =
      Boolean(grant.workspaceSlug) && !workspaceOptions.some((workspace) => workspace.slug === grant.workspaceSlug);

    return (
      <div key={grant.id} className="flex flex-wrap items-start gap-2">
        <select
          aria-label="Workspace to join"
          className="w-44 rounded-md border border-strong bg-surface-1 px-2 py-1"
          value={grant.workspaceSlug}
          onChange={(event) => updateGrant(row.id, grant.id, { workspaceSlug: event.target.value })}
          disabled={!isConfigurationEditable}
        >
          <option value="">Invite by hand</option>
          {isUnknownSlug && <option value={grant.workspaceSlug}>{grant.workspaceSlug} (not on this instance)</option>}
          {workspaceOptions.map((workspace) => (
            <option key={workspace.id} value={workspace.slug}>
              {workspace.name}
            </option>
          ))}
        </select>

        <select
          aria-label="Workspace role"
          className="w-28 rounded-md border border-strong bg-surface-1 px-2 py-1"
          value={grant.workspaceRole}
          onChange={(event) => updateGrant(row.id, grant.id, { workspaceRole: event.target.value as TRoleName })}
          disabled={!isConfigurationEditable || !grant.workspaceSlug}
        >
          {ROLE_NAMES.map((role) => (
            <option key={role} value={role}>
              {ROLE_LABELS[role]}
            </option>
          ))}
        </select>

        <input
          aria-label="Project identifier"
          className="w-28 rounded-md border border-strong bg-surface-1 px-2 py-1 uppercase"
          placeholder="PLAT"
          value={grant.projectIdentifier}
          onChange={(event) => updateGrant(row.id, grant.id, { projectIdentifier: event.target.value })}
          disabled={!isConfigurationEditable || !grant.workspaceSlug}
        />

        <select
          aria-label="Project role"
          className="w-28 rounded-md border border-strong bg-surface-1 px-2 py-1"
          value={grant.projectRole}
          onChange={(event) => updateGrant(row.id, grant.id, { projectRole: event.target.value as TRoleName })}
          disabled={!isConfigurationEditable || !grant.projectIdentifier}
        >
          {ROLE_NAMES.map((role) => (
            <option key={role} value={role}>
              {ROLE_LABELS[role]}
            </option>
          ))}
        </select>

        <button
          type="button"
          aria-label="Remove workspace"
          className="mt-1 text-tertiary hover:text-danger-primary"
          onClick={() => updateRow(row.id, { grants: row.grants.filter((candidate) => candidate.id !== grant.id) })}
          disabled={!isConfigurationEditable}
        >
          <Trash2 className="size-4" />
        </button>
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <p className="max-w-3xl text-13 text-tertiary">
        One row per email domain. A pinned domain accepts only the providers you tick — password sign-in and magic codes
        are refused for it, on both sign-up and sign-in, so nobody can claim a colleague&apos;s address through a weaker
        route. Matching is exact, so <CodeBlock darkerShade>sub.corp.com</CodeBlock> needs its own row.
      </p>

      {isLoadingWorkspaces ? (
        <Loader className="space-y-3">
          <Loader.Item height="40px" />
          <Loader.Item height="40px" />
        </Loader>
      ) : (
        <div className="flex flex-col gap-4">
          {rows.map((row) => (
            <div key={row.id} className="flex flex-col gap-3 rounded-md border border-subtle p-4">
              <div className="flex flex-wrap items-center gap-4">
                <input
                  aria-label="Email domain"
                  className="w-56 rounded-md border border-strong bg-surface-1 px-2 py-1"
                  placeholder="corp.com"
                  value={row.domain}
                  onChange={(event) => updateRow(row.id, { domain: event.target.value })}
                  disabled={!isConfigurationEditable}
                />
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  {ALL_PROVIDERS.map((provider) => (
                    <label key={provider} className="flex items-center gap-1 text-11">
                      <input
                        type="checkbox"
                        checked={row.providers.includes(provider)}
                        onChange={() => toggleProvider(row, provider)}
                        disabled={!isConfigurationEditable}
                      />
                      {provider}
                    </label>
                  ))}
                </div>
                <button
                  type="button"
                  aria-label="Remove domain"
                  className="ml-auto text-tertiary hover:text-danger-primary"
                  onClick={() => {
                    setRows((previous) => previous.filter((candidate) => candidate.id !== row.id));
                    markDirty();
                  }}
                  disabled={!isConfigurationEditable}
                >
                  <Trash2 className="size-4" />
                </button>
              </div>

              {row.providers.length === 0 && (
                <span className="text-11 text-tertiary">None ticked — any of Google, OIDC or SAML.</span>
              )}

              <div className="flex flex-col gap-2 border-t border-subtle pt-3">
                {row.grants.length === 0 && (
                  <span className="text-11 text-tertiary">
                    Nobody joins anything automatically. Invite people by hand, or add a workspace below.
                  </span>
                )}
                {row.grants.map((grant) => renderGrant(row, grant))}
                <div>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => updateRow(row.id, { grants: [...row.grants, emptyGrant()] })}
                    disabled={!isConfigurationEditable}
                  >
                    <Plus className="size-4" /> Add a workspace
                  </Button>
                </div>
              </div>
            </div>
          ))}

          {rows.length === 0 && (
            <p className="py-6 text-center text-13 text-tertiary">
              No domain is pinned. Everyone signs in with whatever methods are enabled.
            </p>
          )}
        </div>
      )}

      <div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            setRows((previous) => [...previous, emptyRow()]);
            markDirty();
          }}
          disabled={!isConfigurationEditable}
        >
          <Plus className="size-4" /> Add a domain
        </Button>
      </div>

      <div className="flex flex-col gap-2 rounded-md border border-subtle p-4 text-11 text-tertiary">
        <span>
          A domain may join more than one workspace — add as many as you need.{" "}
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
