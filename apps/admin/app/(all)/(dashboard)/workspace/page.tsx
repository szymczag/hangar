/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useId, useState } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import useSWR from "swr";
import { LoadingOutline as LoaderIcon } from "@makeplane/propel/icons";
// types
import { Button } from "@makeplane/propel/components/button";
import { InputField } from "@makeplane/propel/components/input-field";
import { Select, SelectContent, SelectItem, SelectList, SelectTrigger } from "@makeplane/propel/components/select";
import { Switch } from "@makeplane/propel/components/switch";
import { EmptyStateCompact } from "@plane/blocks/empty-state";
import { useTranslation } from "@plane/i18n";
import type { TInstanceConfigurationKeys } from "@plane/types";
import { cn } from "@plane/utils";
// components
import { PageWrapper } from "@/components/common/page-wrapper";
import { Skeleton } from "@plane/blocks/skeleton";
import { WorkspaceListItem } from "@/components/workspace/list-item";
import { setPromiseToast } from "@plane/blocks/toast";
// helpers
import { configurationErrorMessage } from "@/helpers/configuration-error";
// hooks
import { useInstance, useWorkspace } from "@/hooks/store";
import { useConfigurationEditable } from "@/hooks/use-configuration-editable";
// types
import type { Route } from "./+types/page";

const START_OF_WEEK_OPTIONS: Record<string, string> = Object.fromEntries(
  ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"].map((day, index) => [
    String(index),
    day,
  ])
);

const THEME_OPTIONS: Record<string, string> = Object.fromEntries(
  ["light", "dark", "light-contrast", "dark-contrast", "system"].map((theme) => [theme, theme])
);

const API_TOKEN_ROLE_OPTIONS: Record<string, string> = {
  "5": "Guest and above",
  "15": "Member and above",
  "20": "Admin only",
};

type TSettingSelectProps = {
  label: string;
  value: string;
  options: Record<string, string>;
  disabled: boolean;
  onChange: (value: string) => void;
  className?: string;
};

function SettingSelect({ label, value, options, disabled, onChange, className }: TSettingSelectProps) {
  const labelId = useId();
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span id={labelId} className="text-body-xs-medium text-primary">
        {label}
      </span>
      <Select items={options} value={value} onValueChange={(next) => onChange(next as string)} disabled={disabled}>
        <SelectTrigger variant="secondary" size="md" width="fit" aria-labelledby={labelId} />
        <SelectContent>
          <SelectList>
            {Object.entries(options).map(([key, optionLabel]) => (
              <SelectItem key={key} value={key} label={optionLabel} />
            ))}
          </SelectList>
        </SelectContent>
      </Select>
    </div>
  );
}

const WorkspaceManagementPage = observer(function WorkspaceManagementPage(_props: Route.ComponentProps) {
  // plane hooks
  const { t } = useTranslation();
  // states
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  // store
  const { formattedConfig, fetchInstanceConfigurations, updateInstanceConfigurations } = useInstance();
  const isConfigurationEditable = useConfigurationEditable();
  const {
    workspaceIds,
    loader: workspaceLoader,
    paginationInfo,
    fetchWorkspaces,
    fetchNextWorkspaces,
  } = useWorkspace();
  // derived values
  const disableWorkspaceCreation = formattedConfig?.DISABLE_WORKSPACE_CREATION ?? "";
  const apiTokenMinimumRole = formattedConfig?.API_TOKEN_MINIMUM_ROLE ?? "5";
  const forcePrivateVisibility = formattedConfig?.FORCE_PRIVATE_VISIBILITY ?? "0";
  const allowMembersToInvite = formattedConfig?.ALLOW_MEMBERS_TO_INVITE ?? "0";
  const defaultWorkspaceId = formattedConfig?.INSTANCE_DEFAULT_WORKSPACE_ID ?? "";
  const defaultStartOfWeek = formattedConfig?.INSTANCE_DEFAULT_START_OF_WEEK ?? "1";
  const defaultTheme = formattedConfig?.INSTANCE_DEFAULT_THEME ?? "light";
  const defaultTimezone = formattedConfig?.INSTANCE_DEFAULT_TIMEZONE ?? "UTC";
  const isControlDisabled = isSubmitting || !isConfigurationEditable;
  const hasNextPage = paginationInfo?.next_page_results && paginationInfo?.next_cursor !== undefined;

  // fetch data
  useSWR("INSTANCE_CONFIGURATIONS", () => fetchInstanceConfigurations());
  useSWR("INSTANCE_WORKSPACES", () => fetchWorkspaces());

  const updateConfig = async (key: TInstanceConfigurationKeys, value: string) => {
    setIsSubmitting(true);

    const payload = {
      [key]: value,
    };

    const updateConfigPromise = updateInstanceConfigurations(payload);

    setPromiseToast(updateConfigPromise, {
      loading: "Saving configuration",
      success: {
        title: "Success",
        message: () => "Configuration saved successfully",
      },
      error: {
        title: "Error",
        message: (error) => configurationErrorMessage(error),
      },
    });

    try {
      await updateConfigPromise;
    } catch {
      // The toast above reports the reason; this only clears the spinner.
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PageWrapper
      header={{
        title: "Workspaces on this instance",
        description: "See all workspaces and control who can create them.",
      }}
    >
      <div className="space-y-3">
        {formattedConfig ? (
          <div className="flex w-full items-start justify-between gap-4 rounded-lg border border-subtle bg-layer-2 px-4 py-3 md:items-center md:gap-8">
            <div className="min-w-0 grow">
              <div className="pb-1 text-body-sm-medium text-primary">Keep everything to the people it belongs to.</div>
              <div className="text-body-xs-regular leading-5 text-tertiary">
                Every project, page and view is private, the choice is not offered, and nothing can be published to the
                internet — the public pages are refused outright. Turning this on also makes what already exists match:
                projects, pages and views become private and published boards stop serving. That part cannot be undone
                by turning it back off, because what each thing used to be readable by is not recorded.
              </div>
            </div>
            <div className={cn("shrink-0", { "opacity-70": isSubmitting })}>
              <Switch
                checked={Boolean(parseInt(forcePrivateVisibility))}
                onCheckedChange={() =>
                  updateConfig("FORCE_PRIVATE_VISIBILITY", parseInt(forcePrivateVisibility) ? "0" : "1")
                }
                size="sm"
                aria-label="Keep everything to the people it belongs to"
                disabled={isControlDisabled}
              />
            </div>
          </div>
        ) : (
          <Skeleton>
            <Skeleton.Item height="50px" width="100%" />
          </Skeleton>
        )}
        {formattedConfig ? (
          <div className="flex w-full flex-col gap-4 rounded-lg border border-subtle bg-layer-2 px-4 py-3">
            <div className="min-w-0 grow">
              <div className="pb-1 text-body-sm-medium text-primary">What a new account starts with.</div>
              <div className="text-body-xs-regular leading-5 text-tertiary">
                Starting values, not rules. Everyone can change these afterwards, and changing them here does not reach
                back into accounts that already exist. Upstream starts the week on Sunday and follows the operating
                system for the theme, which means every new person changes the same settings by hand.
              </div>
            </div>
            <div className="flex flex-wrap items-end gap-4">
              <SettingSelect
                label="First day of the week"
                value={defaultStartOfWeek}
                options={START_OF_WEEK_OPTIONS}
                disabled={isControlDisabled}
                onChange={(value) => updateConfig("INSTANCE_DEFAULT_START_OF_WEEK", value)}
              />
              <SettingSelect
                label="Theme"
                value={defaultTheme}
                options={THEME_OPTIONS}
                disabled={isControlDisabled}
                onChange={(value) => updateConfig("INSTANCE_DEFAULT_THEME", value)}
              />
              <div className="w-56">
                <InputField
                  size="md"
                  orientation="vertical"
                  label="Timezone"
                  value={defaultTimezone}
                  placeholder="Europe/Warsaw"
                  onChange={(event) => updateConfig("INSTANCE_DEFAULT_TIMEZONE", event.target.value)}
                  disabled={isControlDisabled}
                />
              </div>
            </div>
          </div>
        ) : (
          <Skeleton>
            <Skeleton.Item height="50px" width="100%" />
          </Skeleton>
        )}
        {formattedConfig ? (
          <div className="flex w-full items-start justify-between gap-4 rounded-lg border border-subtle bg-layer-2 px-4 py-3 md:items-center md:gap-8">
            <div className="flex min-w-0 grow items-center gap-4">
              <div className="min-w-0 grow">
                <div className="pb-1 text-body-sm-medium text-primary">
                  Prevent anyone else from creating a workspace.
                </div>
                <div className="text-body-xs-regular leading-5 text-tertiary">
                  Toggling this on will let only you create workspaces. You will have to invite users to new workspaces.
                  Left off, anyone with an account — including someone who signed up through SSO and was never invited
                  anywhere — can create their own workspace on this instance.
                </div>
              </div>
            </div>
            <div className={cn("shrink-0", { "opacity-70": isSubmitting })}>
              <div className="flex items-center gap-4">
                <Switch
                  checked={Boolean(parseInt(disableWorkspaceCreation))}
                  onCheckedChange={() => {
                    if (Boolean(parseInt(disableWorkspaceCreation)) === true) {
                      updateConfig("DISABLE_WORKSPACE_CREATION", "0");
                    } else {
                      updateConfig("DISABLE_WORKSPACE_CREATION", "1");
                    }
                  }}
                  size="sm"
                  aria-label="Prevent anyone else from creating a workspace"
                  disabled={isControlDisabled}
                />
              </div>
            </div>
          </div>
        ) : (
          <Skeleton>
            <Skeleton.Item height="50px" width="100%" />
          </Skeleton>
        )}
        {formattedConfig && (
          <div className="flex w-full items-start justify-between gap-4 rounded-lg border border-subtle bg-layer-2 px-4 py-3 md:items-center md:gap-8">
            <div className="min-w-0 grow">
              <div className="pb-1 text-body-sm-medium text-primary">Role required to create an API token</div>
              <div className="text-body-xs-regular leading-5 text-tertiary">
                A token acts in one workspace and carries its owner&apos;s permissions there, so this decides who can
                hand a script the same access they have. Raising it does not revoke tokens that already exist.
              </div>
            </div>
            <SettingSelect
              label="Minimum role"
              className={cn("shrink-0", { "opacity-70": isSubmitting })}
              value={apiTokenMinimumRole}
              options={API_TOKEN_ROLE_OPTIONS}
              disabled={isControlDisabled}
              onChange={(value) => updateConfig("API_TOKEN_MINIMUM_ROLE", value)}
            />
          </div>
        )}
        {formattedConfig && (
          <div className="flex w-full items-start justify-between gap-4 rounded-lg border border-subtle bg-layer-2 px-4 py-3 md:items-center md:gap-8">
            <div className="min-w-0 grow">
              <div className="pb-1 text-body-sm-medium text-primary">Members can invite to workspaces</div>
              <div className="text-body-xs-regular leading-5 text-tertiary">
                When off, only workspace admins can invite people and change or withdraw pending invitations. When on,
                members can invite too — at most at their own role — and change or withdraw the invitations they sent,
                not anyone else&apos;s. Guests can never invite. Turning it off takes the right back from members at
                once; invitations already sent stay valid until an admin withdraws them.
              </div>
            </div>
            <div className={cn("shrink-0", { "opacity-70": isSubmitting })}>
              <Switch
                checked={allowMembersToInvite.trim() === "1"}
                onCheckedChange={() =>
                  updateConfig("ALLOW_MEMBERS_TO_INVITE", allowMembersToInvite.trim() === "1" ? "0" : "1")
                }
                size="sm"
                aria-label="Members can invite to workspaces"
                disabled={isControlDisabled}
              />
            </div>
          </div>
        )}
        {workspaceLoader !== "init-loader" ? (
          <>
            <div className="flex flex-col gap-3 pt-6 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-col items-start gap-x-2">
                <div className="flex items-center gap-2 text-body-md-medium">
                  All workspaces on this instance <span className="text-tertiary">• {workspaceIds.length}</span>
                  {workspaceLoader && ["mutation", "pagination"].includes(workspaceLoader) && (
                    <LoaderIcon className="h-4 w-4 animate-spin" />
                  )}
                </div>
                <div className="text-body-xs-regular leading-5 text-tertiary">
                  You can&apos;t yet delete workspaces and you can only go to the workspace if you are an Admin or a
                  Member. Choose one workspace to use compact links such as /i/AA-123. Clearing the choice restores
                  workspace-qualified links everywhere.
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  stretch="auto"
                  nativeButton={false}
                  render={<Link href="/workspace/create" />}
                  label="Create workspace"
                />
              </div>
            </div>
            <div className="flex flex-col gap-4 py-2">
              {workspaceIds.length > 0 ? (
                workspaceIds.map((workspaceId) => (
                  <WorkspaceListItem
                    key={workspaceId}
                    workspaceId={workspaceId}
                    isDefaultForShortLinks={workspaceId === defaultWorkspaceId}
                    isUpdatingDefault={isSubmitting}
                    canUpdateDefault={isConfigurationEditable}
                    onDefaultChange={(selected) =>
                      updateConfig("INSTANCE_DEFAULT_WORKSPACE_ID", selected ? workspaceId : "")
                    }
                  />
                ))
              ) : paginationInfo ? (
                <EmptyStateCompact
                  assetKey="project"
                  title={t("instance_workspaces.empty_state.title")}
                  description={t("instance_workspaces.empty_state.description")}
                  rootClassName="rounded-lg border border-subtle py-10"
                />
              ) : null}
            </div>
            {hasNextPage && (
              <div className="flex justify-center">
                <Button
                  variant="ghost"
                  size="md"
                  stretch="auto"
                  onClick={() => fetchNextWorkspaces()}
                  loading={workspaceLoader === "pagination"}
                  label="Load more"
                />
              </div>
            )}
          </>
        ) : (
          <Skeleton className="space-y-10 py-8">
            <Skeleton.Item height="24px" width="20%" />
            <Skeleton.Item height="92px" width="100%" />
            <Skeleton.Item height="92px" width="100%" />
            <Skeleton.Item height="92px" width="100%" />
          </Skeleton>
        )}
      </div>
    </PageWrapper>
  );
});

export const meta: Route.MetaFunction = () => [{ title: "Workspace Management - God Mode" }];

export default WorkspaceManagementPage;
