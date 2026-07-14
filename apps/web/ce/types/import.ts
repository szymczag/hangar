/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TImportDiagnostic = {
  level: "warning" | "error";
  code: string;
  message: string;
  row: number | null;
  field: string | null;
};

export type TTodoistModuleConflict = {
  row: number;
  name: string;
  module_id: string;
};

export type TTodoistImportPreview = {
  digest: string;
  counts: Record<string, number>;
  diagnostics: TImportDiagnostic[];
  assignees: string[];
  module_conflicts: TTodoistModuleConflict[];
  project_note_action: "set" | "skip";
  enables_modules: boolean;
  duplicate: boolean;
};

export type TImportJob = {
  id: string;
  provider: "todoist_csv";
  status: "queued" | "processing" | "completed" | "failed" | "cancelled";
  project: string;
  project_detail: { id: string; name: string; identifier: string };
  stats: Record<string, number>;
  errors: TImportDiagnostic[];
  reason: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
};

export type TImportJobList = {
  results: TImportJob[];
  next_page_results: boolean;
  prev_page_results: boolean;
  next_cursor: string;
  prev_cursor: string;
};

export type TTodoistImportConfig = {
  assignee_mapping: Record<string, string>;
  module_conflicts: Record<string, { action: "reuse"; module_id: string } | { action: "rename"; name: string }>;
  allow_duplicate?: boolean;
};
