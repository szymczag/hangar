/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import useSWR from "swr";
import { Loader as LoaderIcon } from "lucide-react";
// types
import { Button, getButtonStyling } from "@plane/propel/button";
import { setPromiseToast } from "@plane/propel/toast";
import type { TInstanceConfigurationKeys } from "@plane/types";
import { Loader, ToggleSwitch } from "@plane/ui";
import { cn } from "@plane/utils";
// components
import { PageWrapper } from "@/components/common/page-wrapper";
import { WorkspaceListItem } from "@/components/workspace/list-item";
// hooks
import { configurationErrorMessage } from "@/helpers/configuration-error";
import { useInstance, useWorkspace } from "@/hooks/store";
import { useConfigurationEditable } from "@/hooks/use-configuration-editable";
// types
import type { Route } from "./+types/page";

const WorkspaceManagementPage = observer(function WorkspaceManagementPage(_props: Route.ComponentProps) {
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
  const defaultStartOfWeek = formattedConfig?.INSTANCE_DEFAULT_START_OF_WEEK ?? "1";
  const defaultTheme = formattedConfig?.INSTANCE_DEFAULT_THEME ?? "light";
  const defaultTimezone = formattedConfig?.INSTANCE_DEFAULT_TIMEZONE ?? "UTC";
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
          <div className={cn("flex w-full items-center gap-14 rounded-sm")}>
            <div className="flex grow items-center gap-4">
              <div className="grow">
                <div className="pb-1 text-16 font-medium">Keep everything to the people it belongs to.</div>
                <div className={cn("text-11 leading-5 font-regular text-tertiary")}>
                  Every project, page and view is private, the choice is not offered, and nothing can be published to
                  the internet — the public pages are refused outright. Turning this on also makes what already exists
                  match: projects, pages and views become private and published boards stop serving. That part cannot be
                  undone by turning it back off, because what each thing used to be readable by is not recorded.
                </div>
              </div>
            </div>
            <div className={`shrink-0 pr-4 ${isSubmitting && "opacity-70"}`}>
              <div className="flex items-center gap-4">
                <ToggleSwitch
                  value={Boolean(parseInt(forcePrivateVisibility))}
                  onChange={() => {
                    if (Boolean(parseInt(forcePrivateVisibility)) === true) {
                      updateConfig("FORCE_PRIVATE_VISIBILITY", "0");
                    } else {
                      updateConfig("FORCE_PRIVATE_VISIBILITY", "1");
                    }
                  }}
                  size="sm"
                  disabled={isSubmitting || !isConfigurationEditable}
                />
              </div>
            </div>
          </div>
        ) : (
          <Loader>
            <Loader.Item height="50px" width="100%" />
          </Loader>
        )}
        {formattedConfig ? (
          <div className="flex w-full flex-col gap-4 rounded-sm">
            <div className="grow">
              <div className="pb-1 text-16 font-medium">What a new account starts with.</div>
              <div className={cn("text-11 leading-5 font-regular text-tertiary")}>
                Starting values, not rules. Everyone can change these afterwards, and changing them here does not reach
                back into accounts that already exist. Upstream starts the week on Sunday and follows the operating
                system for the theme, which means every new person changes the same settings by hand.
              </div>
            </div>
            <div className="flex flex-wrap items-end gap-4">
              <div className="flex flex-col gap-1">
                <span className="text-11 text-tertiary">First day of the week</span>
                <select
                  className="w-44 rounded-md border border-strong bg-surface-1 px-3 py-2 text-13"
                  value={defaultStartOfWeek}
                  onChange={(event) => updateConfig("INSTANCE_DEFAULT_START_OF_WEEK", event.target.value)}
                  disabled={isSubmitting || !isConfigurationEditable}
                >
                  {["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"].map((day, index) => (
                    <option key={day} value={String(index)}>
                      {day}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-11 text-tertiary">Theme</span>
                <select
                  className="w-44 rounded-md border border-strong bg-surface-1 px-3 py-2 text-13"
                  value={defaultTheme}
                  onChange={(event) => updateConfig("INSTANCE_DEFAULT_THEME", event.target.value)}
                  disabled={isSubmitting || !isConfigurationEditable}
                >
                  {["light", "dark", "light-contrast", "dark-contrast", "system"].map((theme) => (
                    <option key={theme} value={theme}>
                      {theme}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-11 text-tertiary">Timezone</span>
                <input
                  className="w-56 rounded-md border border-strong bg-surface-1 px-3 py-2 text-13"
                  value={defaultTimezone}
                  placeholder="Europe/Warsaw"
                  onChange={(event) => updateConfig("INSTANCE_DEFAULT_TIMEZONE", event.target.value)}
                  disabled={isSubmitting || !isConfigurationEditable}
                />
              </div>
            </div>
          </div>
        ) : (
          <Loader>
            <Loader.Item height="50px" width="100%" />
          </Loader>
        )}
        {formattedConfig ? (
          <div className={cn("flex w-full items-center gap-14 rounded-sm")}>
            <div className="flex grow items-center gap-4">
              <div className="grow">
                <div className="pb-1 text-16 font-medium">Prevent anyone else from creating a workspace.</div>
                <div className={cn("text-11 leading-5 font-regular text-tertiary")}>
                  Toggling this on will let only you create workspaces. You will have to invite users to new workspaces.
                  Left off, anyone with an account — including someone who signed up through SSO and was never invited
                  anywhere — can create their own workspace on this instance.
                </div>
              </div>
            </div>
            <div className={`shrink-0 pr-4 ${isSubmitting && "opacity-70"}`}>
              <div className="flex items-center gap-4">
                <ToggleSwitch
                  value={Boolean(parseInt(disableWorkspaceCreation))}
                  onChange={() => {
                    if (Boolean(parseInt(disableWorkspaceCreation)) === true) {
                      updateConfig("DISABLE_WORKSPACE_CREATION", "0");
                    } else {
                      updateConfig("DISABLE_WORKSPACE_CREATION", "1");
                    }
                  }}
                  size="sm"
                  disabled={isSubmitting || !isConfigurationEditable}
                />
              </div>
            </div>
          </div>
        ) : (
          <Loader>
            <Loader.Item height="50px" width="100%" />
          </Loader>
        )}

        {formattedConfig && (
          <div className={cn("flex w-full items-center gap-14 rounded-sm border-t border-subtle pt-4")}>
            <div className="flex grow items-center gap-4">
              <div className="grow">
                <div className="pb-1 text-16 font-medium">Role required to create an API token</div>
                <div className={cn("text-11 leading-5 font-regular text-tertiary")}>
                  A token acts in one workspace and carries its owner&apos;s permissions there, so this decides who can
                  hand a script the same access they have. Raising it does not revoke tokens that already exist.
                </div>
              </div>
            </div>
            <div className={`shrink-0 pr-4 ${isSubmitting && "opacity-70"}`}>
              <select
                aria-label="Role required to create an API token"
                className="rounded-md border border-strong bg-surface-1 px-3 py-2 text-14"
                value={apiTokenMinimumRole}
                onChange={(event) => updateConfig("API_TOKEN_MINIMUM_ROLE", event.target.value)}
                disabled={isSubmitting || !isConfigurationEditable}
              >
                <option value="5">Guest and above</option>
                <option value="15">Member and above</option>
                <option value="20">Admin only</option>
              </select>
            </div>
          </div>
        )}
        {workspaceLoader !== "init-loader" ? (
          <>
            <div className="flex items-center justify-between gap-2 pt-6">
              <div className="flex flex-col items-start gap-x-2">
                <div className="flex items-center gap-2 text-16 font-medium">
                  All workspaces on this instance <span className="text-tertiary">• {workspaceIds.length}</span>
                  {workspaceLoader && ["mutation", "pagination"].includes(workspaceLoader) && (
                    <LoaderIcon className="h-4 w-4 animate-spin" />
                  )}
                </div>
                <div className={cn("text-11 leading-5 font-regular text-tertiary")}>
                  You can&apos;t yet delete workspaces and you can only go to the workspace if you are an Admin or a
                  Member.
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Link href="/workspace/create" className={getButtonStyling("primary", "base")}>
                  Create workspace
                </Link>
              </div>
            </div>
            <div className="flex flex-col gap-4 py-2">
              {workspaceIds.map((workspaceId) => (
                <WorkspaceListItem key={workspaceId} workspaceId={workspaceId} />
              ))}
            </div>
            {hasNextPage && (
              <div className="flex justify-center">
                <Button
                  variant="link"
                  size="lg"
                  onClick={() => fetchNextWorkspaces()}
                  disabled={workspaceLoader === "pagination"}
                >
                  Load more
                  {workspaceLoader === "pagination" && <LoaderIcon className="h-3 w-3 animate-spin" />}
                </Button>
              </div>
            )}
          </>
        ) : (
          <Loader className="space-y-10 py-8">
            <Loader.Item height="24px" width="20%" />
            <Loader.Item height="92px" width="100%" />
            <Loader.Item height="92px" width="100%" />
            <Loader.Item height="92px" width="100%" />
          </Loader>
        )}
      </div>
    </PageWrapper>
  );
});

export const meta: Route.MetaFunction = () => [{ title: "Workspace Management - God Mode" }];

export default WorkspaceManagementPage;
