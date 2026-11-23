/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane imports
import { Collapsible } from "@makeplane/propel/components/collapsible";
import { useTranslation } from "@plane/i18n";
import { EmptyStateCompact } from "@plane/blocks/empty-state";
// components
import { CountChip } from "@/components/common/count-chip";
import { MembersSettingsLoader } from "@/components/ui/loader/settings/members";
// hooks
import { useMember } from "@/hooks/store/use-member";
// local imports
import { WorkspaceInvitationsListItem } from "./invitations-list-item";
import { WorkspaceMembersListItem } from "./members-list-item";

/** Shown only to callers the invitation list endpoint answers. */
const PendingInvitations = observer(function PendingInvitations(props: { invitationIds: string[] }) {
  const { invitationIds } = props;
  const [showPendingInvites, setShowPendingInvites] = useState<boolean>(true);
  const { t } = useTranslation();

  if (invitationIds.length === 0) return null;

  return (
    <div className="shrink-0 pt-4">
      <Collapsible
        open={showPendingInvites}
        onOpenChange={setShowPendingInvites}
        trigger={
          <span className="flex items-center gap-2">
            <span className="text-h5-medium">{t("workspace_settings.settings.members.pending_invites")}</span>
            <CountChip count={invitationIds.length} />
          </span>
        }
      >
        <div className="flex flex-col items-center gap-1.5 rounded-md bg-surface-1 py-1.5">
          {invitationIds.map((invitationId) => (
            <WorkspaceInvitationsListItem key={invitationId} invitationId={invitationId} />
          ))}
        </div>
      </Collapsible>
    </div>
  );
});

export const WorkspaceMembersList = observer(function WorkspaceMembersList(props: {
  searchQuery: string;
  /** Admins, and members where the instance lets them invite; the list endpoint refuses everyone else. */
  canSeeInvitations: boolean;
}) {
  const { searchQuery, canSeeInvitations } = props;

  // router
  const { workspaceSlug } = useParams();
  // store hooks
  const {
    workspace: {
      fetchWorkspaceMembers,
      fetchWorkspaceMemberInvitations,
      workspaceMemberIds,
      getFilteredWorkspaceMemberIds,
      getSearchedWorkspaceMemberIds,
      workspaceMemberInvitationIds,
      getSearchedWorkspaceInvitationIds,
      getWorkspaceMemberDetails,
    },
  } = useMember();
  const { t } = useTranslation();
  // fetching workspace invitations
  const slug = workspaceSlug?.toString();
  useSWR(
    // The flag is in the key so the invitations arrive once the instance config says they may be read.
    slug ? ["WORKSPACE_MEMBERS_AND_MEMBER_INVITATIONS", slug, canSeeInvitations] : null,
    async ([, key, withInvitations]: [string, string, boolean]) => {
      if (withInvitations) await fetchWorkspaceMemberInvitations(key);
      await fetchWorkspaceMembers(key);
    }
  );

  if (!workspaceMemberIds && !workspaceMemberInvitationIds) return <MembersSettingsLoader />;

  // derived values
  const filteredMemberIds = workspaceSlug ? getFilteredWorkspaceMemberIds(workspaceSlug.toString()) : [];
  const searchedMemberIds = searchQuery ? getSearchedWorkspaceMemberIds(searchQuery) : filteredMemberIds;
  const searchedInvitationsIds = getSearchedWorkspaceInvitationIds(searchQuery);
  const memberDetails = searchedMemberIds
    ?.map((memberId) => getWorkspaceMemberDetails(memberId))
    // oxlint-disable-next-line unicorn/no-array-sort -- sorts the fresh array map() just returned; the lib target has no toSorted
    .sort((a, b) => {
      if (a?.is_active && !b?.is_active) return -1;
      if (!a?.is_active && b?.is_active) return 1;
      return 0;
    });

  return (
    <>
      <div className="flex min-h-[50vh] grow flex-col overflow-hidden">
        {searchedMemberIds?.length !== 0 && <WorkspaceMembersListItem memberDetails={memberDetails ?? []} />}
        {searchedInvitationsIds?.length === 0 && searchedMemberIds?.length === 0 && (
          <EmptyStateCompact
            assetKey="search-compact"
            title={t("no_matching_members")}
            rootClassName="grow rounded-lg border border-subtle py-10"
          />
        )}
      </div>
      {canSeeInvitations && <PendingInvitations invitationIds={searchedInvitationsIds ?? []} />}
    </>
  );
});
