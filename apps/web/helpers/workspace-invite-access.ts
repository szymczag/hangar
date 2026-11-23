/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { EUserPermissions } from "@plane/constants";

/**
 * Who may invite people to a workspace and manage its pending invitations.
 *
 * Mirrors `WorkspaceInvitePermission` in `plane/app/permissions/workspace_invite.py`:
 * admins always; members only where the instance reports `members_can_invite`,
 * and then only for the invitations they sent; guests never. The server
 * decides either way — this keeps the interface from offering what it refuses.
 */
export const canInviteToWorkspace = (role: number | undefined, membersCanInvite: boolean | undefined): boolean =>
  role === EUserPermissions.ADMIN || (role === EUserPermissions.MEMBER && membersCanInvite === true);

export const canManageWorkspaceInvitation = (
  role: number | undefined,
  membersCanInvite: boolean | undefined,
  invitationSender: string | null | undefined,
  currentUserId: string | undefined
): boolean => {
  if (role === EUserPermissions.ADMIN) return true;
  if (!canInviteToWorkspace(role, membersCanInvite)) return false;
  // An invitation with no recorded sender is left to the admins, as on the server.
  return !!invitationSender && !!currentUserId && invitationSender === currentUserId;
};
