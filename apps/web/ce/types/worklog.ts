/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TIssueWorklog = {
  id: string;
  duration: number; // minutes
  description: string;
  logged_by: string | null;
  issue: string;
  project: string;
  workspace: string;
  created_at: string;
  updated_at: string;
};

export type TIssueWorklogsResponse = {
  worklogs: TIssueWorklog[];
  total_duration: number; // minutes
};
