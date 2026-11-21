/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import {
  AiStarFourOutline,
  LockOutline,
  MailOutline,
  MembersOutline,
  PaletteOutline,
  SettingsOutline,
  UpdatesOutline,
  WorkspaceOutline,
} from "@makeplane/propel/icons";
// types
import type { TSidebarMenuItem } from "./types";

export type TCoreSidebarMenuKey =
  | "general"
  | "email"
  | "workspace"
  | "users"
  | "authentication"
  | "branding"
  | "maintenance"
  | "ai";

export const coreSidebarMenuLinks: Record<TCoreSidebarMenuKey, TSidebarMenuItem> = {
  general: {
    Icon: SettingsOutline,
    name: "General",
    description: "Identify your instances and get key details.",
    href: `/general/`,
  },
  email: {
    Icon: MailOutline,
    name: "Email",
    description: "Configure your SMTP controls.",
    href: `/email/`,
  },
  workspace: {
    Icon: WorkspaceOutline,
    name: "Workspaces",
    description: "Manage all workspaces on this instance.",
    href: `/workspace/`,
  },
  users: {
    Icon: MembersOutline,
    name: "Users",
    description: "See who has an account and how they sign in.",
    href: `/users/`,
  },
  authentication: {
    Icon: LockOutline,
    name: "Authentication",
    description: "Configure authentication modes.",
    href: `/authentication/`,
  },
  branding: {
    Icon: PaletteOutline,
    name: "Branding",
    description: "Your logo and wording on the sign-in page.",
    href: `/branding/`,
  },
  maintenance: {
    Icon: UpdatesOutline,
    name: "Maintenance notice",
    description: "Announce downtime across the instance.",
    href: `/maintenance/`,
  },
  ai: {
    Icon: AiStarFourOutline,
    name: "Artificial intelligence",
    description: "Configure your OpenAI creds.",
    href: `/ai/`,
  },
};
