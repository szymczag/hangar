/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TIssuePropertyType = "text" | "number" | "date" | "boolean" | "select" | "multi_select" | "member";

export type TIssuePropertyOptionExt = {
  id: string;
  name: string;
  sort_order: number;
  is_active: boolean;
  is_default: boolean;
  logo_props: Record<string, unknown>;
  property: string;
};

export type TIssuePropertyExt = {
  id: string;
  display_name: string;
  description: string;
  property_type: TIssuePropertyType;
  is_multi: boolean;
  is_required: boolean;
  is_active: boolean;
  default_value: string[];
  settings: Record<string, unknown>;
  logo_props: Record<string, unknown>;
  sort_order: number;
  issue_type: string;
  options: TIssuePropertyOptionExt[];
};

export type TIssueTypeExt = {
  id: string;
  name: string;
  description: string;
  logo_props: Record<string, unknown>;
  is_epic: boolean;
  is_default: boolean;
  is_active: boolean;
  level: number;
  system_key: "task" | "epic" | "workshop" | null;
  properties?: TIssuePropertyExt[];
};
