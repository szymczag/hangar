// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * The workspace and account settings that guard secrets and destructive actions.
 *
 * These pages moved to upstream's Propel markup in phase 3b. Each check below is
 * a Hangar rule the markup could drop without a type error or a failing render:
 *
 * - deleting a workspace asks for its name and for "delete my workspace";
 * - a new API token names the workspace it acts in, offered only where the
 *   person's role allows minting one, and its secret never reaches the list
 *   cache that outlives the dialog;
 * - the invite dialog checks addresses against the workspace's invite policy
 *   and offers no role above the inviter's;
 * - inviting is offered to admins, and to members only where the instance
 *   reports `members_can_invite`; a member manages only the invitations they sent;
 * - the password change uses the async zxcvbn estimate (15 characters, S9) and
 *   shows a federated account the notice instead of the form (S10).
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (relative) => readFileSync(new URL(`../${relative}`, import.meta.url), "utf8");

test("deleting a workspace needs its name and the confirmation phrase", () => {
  const source = read("components/workspace/delete-workspace-form.tsx");
  assert.match(source, /<TypeToConfirmDialog/, "the confirmation dialog must stay");
  assert.match(source, /expectedValue: data\?\.name \?\? ""/, "one field must expect the workspace's own name");
  assert.match(source, /DELETE_WORKSPACE_CONFIRM_PHRASE = "delete my workspace"/);
  assert.match(
    source,
    /expectedValue: DELETE_WORKSPACE_CONFIRM_PHRASE/,
    "a second field must expect the fixed phrase, as Hangar always has"
  );
  assert.match(source, /onConfirm=\{onSubmit\}/, "deleteWorkspace must run only from the confirmed dialog");
});

test("the delete section is rendered only for workspace admins", () => {
  const source = read("components/workspace/settings/workspace-details.tsx");
  assert.match(source, /isAdmin = allowPermissions\(\[EUserPermissions\.ADMIN\], EUserPermissionsLevel\.WORKSPACE\)/);
  assert.match(source, /\{isAdmin && \(\s*<div[^>]*>\s*<DeleteWorkspaceSection/);
});

test("a new API token names a workspace where the role allows one", () => {
  const form = read("components/api-token/modal/form.tsx");
  assert.match(form, /workspacesAllowingApiTokens\(workspaces, config\?\.api_token_minimum_role\)/);
  assert.match(form, /name="workspace_slug"\s*rules=\{\{ required:/, "the workspace must be required");
  assert.match(form, /workspace_slug: data\.workspace_slug/, "the workspace must reach the request");

  const page = read("components/settings/profile/content/pages/api-tokens.tsx");
  assert.match(page, /canCreateToken = eligibleWorkspaces\.length > 0/);
  for (const offer of page.matchAll(/setIsCreateTokenModalOpen\(true\)/g)) {
    const before = page.slice(Math.max(0, offer.index - 600), offer.index);
    assert.match(before, /canCreateToken/, "every way into the create dialog must be behind canCreateToken");
  }
});

test("the token secret is shown once and kept out of the list cache", () => {
  const modal = read("components/api-token/modal/create-token-modal.tsx");
  assert.match(modal, /const \{ token: _secret, \.\.\.listedToken \} = res;/);
  assert.match(modal, /return \[listedToken, \.\.\.prevData\];/, "the cached row must be the one without the secret");
  assert.doesNotMatch(modal, /\[res, \.\.\.prevData\]/);
  assert.match(modal, /setGeneratedToken\(null\)/, "closing the dialog must drop the generated token");
  assert.doesNotMatch(modal, /console\./, "the token must never be logged");
});

test("invitations follow the invite policy and the inviter's role", () => {
  const modal = read("components/workspace/members/invite-modal.tsx");
  assert.match(modal, /workspaceService\.workspaceInvitationPolicy\(/);
  assert.match(modal, /invitePolicy=\{invitePolicy\}/, "the policy must reach the fields");

  const fields = read("components/workspace/invite-modal/fields.tsx");
  assert.match(fields, /validate: validateAgainstPolicy/);
  assert.match(fields, /inviteRejection\(value, invitePolicy\)/);
  assert.match(
    fields,
    /\.filter\(\(role\) => !!currentWorkspaceRole && currentWorkspaceRole >= role\.key\)/,
    "no role above the inviter's own may be offered"
  );
});

test("inviting is offered only where the server accepts it", () => {
  const helper = read("helpers/workspace-invite-access.ts");
  assert.match(
    helper,
    /role === EUserPermissions\.ADMIN \|\| \(role === EUserPermissions\.MEMBER && membersCanInvite === true\)/,
    "members invite only where the instance says so; guests never"
  );
  assert.match(helper, /invitationSender === currentUserId/, "a member manages only what they sent");

  const page = read("app/(all)/[workspaceSlug]/(settings)/settings/(workspace)/members/page.tsx");
  assert.match(
    page,
    /canInviteToWorkspace\(workspaceInfoBySlug\(workspaceSlug\)\?\.role, config\?\.members_can_invite\)/
  );
  for (const offer of page.matchAll(/setInviteModal\(true\)/g)) {
    const before = page.slice(Math.max(0, offer.index - 400), offer.index);
    assert.match(before, /\{canInvite && \(/, "every way into the invite dialog must be behind canInvite");
  }
  assert.match(page, /<WorkspaceMembersList searchQuery=\{searchQuery\} canSeeInvitations=\{canInvite\} \/>/);

  const list = read("components/workspace/settings/members-list.tsx");
  assert.match(
    list,
    /if \(canSeeInvitations\) await fetchWorkspaceMemberInvitations\(/,
    "the invitation list is refused to others, so it must not be requested"
  );
  assert.match(list, /\{canSeeInvitations && searchedInvitationsIds/);

  const row = read("components/workspace/settings/invitations-list-item.tsx");
  assert.match(row, /const canManageInvitation = canManageWorkspaceInvitation\(/);
  assert.match(row, /const hasRoleChangeAccess = canManageInvitation;/);
  assert.match(row, /\{canManageInvitation && \(\s*<Menu>/, "remove and copy link follow the same rule");

  const sidebar = read("components/workspace/sidebar/dropdown-item.tsx");
  assert.match(sidebar, /canInviteToWorkspace\(workspace\?\.role, config\?\.members_can_invite\)/);
  assert.match(sidebar, /\{canInvite && \(\s*<Menu\.Item/);

  const home = read("components/home/widgets/empty-states/no-projects.tsx");
  assert.match(home, /link: `\/\$\{workspaceSlug\}\/settings\/members`,\s*disabled: !canInvite,/);
});

test("the password change keeps Hangar's strength rules and federated notice", () => {
  const source = read("components/settings/profile/content/pages/security.tsx");
  assert.match(source, /import \{ PasswordStrengthIndicator, usePasswordStrength \} from "@plane\/blocks\/auth";/);
  assert.doesNotMatch(source, /getPasswordStrength\(/, "upstream's synchronous estimate must not come back");
  assert.match(source, /passwordStrength\.strength != E_PASSWORD_STRENGTH\.STRENGTH_VALID \|\|/);
  assert.match(source, /oldPasswordRequired = !currentUser\?\.is_password_autoset/);
  assert.match(source, /if \(currentUser\?\.is_federated\) \{/);
  assert.match(source, /requestCSRFToken\(\)/, "the change must carry a CSRF token");
  assert.equal(source.match(/<EmailSecuritySettings \/>/g)?.length, 2, "both branches keep the email security page");
});
