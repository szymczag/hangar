/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { AlertTriangle, CheckCircle2, FileText, Loader2 } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CustomSelect } from "@plane/ui";
import { useMember } from "@/hooks/store/use-member";
import { useProject } from "@/hooks/store/use-project";
import { importService } from "@/plane-web/services/import.service";
import type { TTodoistImportConfig, TTodoistImportPreview } from "@/plane-web/types/import";

type Props = { workspaceSlug: string };

const ACTIVE_STATUSES = new Set(["queued", "processing"]);

const errorMessage = (error: unknown): string => {
  if (typeof error !== "object" || error === null) return "The import request failed.";
  const payload = error as { error?: { message?: string } | string };
  return typeof payload.error === "string" ? payload.error : payload.error?.message || "The import request failed.";
};

export const TodoistImport = observer(function TodoistImport({ workspaceSlug }: Props) {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<TTodoistImportPreview | null>(null);
  const [assigneeMapping, setAssigneeMapping] = useState<Record<string, string>>({});
  const [renamedModules, setRenamedModules] = useState<Record<number, string>>({});
  const [allowDuplicate, setAllowDuplicate] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { workspaceProjectIds, getProjectById } = useProject();
  const { project: projectMembers } = useMember();
  const memberIds = projectId ? projectMembers.getProjectMemberIds(projectId, false) : null;

  const { data: jobs, mutate } = useSWR(
    workspaceSlug ? `todoist-imports-${workspaceSlug}` : null,
    () => importService.list(workspaceSlug),
    {
      refreshInterval: (data) => (data?.results.some((job) => ACTIVE_STATUSES.has(job.status)) ? 3000 : 0),
    }
  );

  useEffect(() => {
    if (projectId) void projectMembers.fetchProjectMembers(workspaceSlug, projectId);
  }, [projectId, projectMembers, workspaceSlug]);

  const projectOptions = useMemo(
    () =>
      (workspaceProjectIds ?? []).map((id) => {
        const project = getProjectById(id);
        return { value: id, label: `${project?.identifier ?? ""} · ${project?.name ?? ""}` };
      }),
    [getProjectById, workspaceProjectIds]
  );

  const resetPreview = () => {
    setPreview(null);
    setAssigneeMapping({});
    setRenamedModules({});
    setAllowDuplicate(false);
  };

  const handlePreview = async () => {
    if (!projectId || !file) return;
    setIsSubmitting(true);
    try {
      const result = await importService.previewTodoist(workspaceSlug, projectId, file);
      setPreview(result);
      setRenamedModules(Object.fromEntries(result.module_conflicts.map((conflict) => [conflict.row, conflict.name])));
    } catch (error) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Could not preview import", message: errorMessage(error) });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleImport = async () => {
    if (!projectId || !file || !preview) return;
    const config: TTodoistImportConfig = {
      assignee_mapping: Object.fromEntries(Object.entries(assigneeMapping).filter(([, value]) => value)),
      module_conflicts: Object.fromEntries(
        preview.module_conflicts.map((conflict) => {
          const name = renamedModules[conflict.row]?.trim();
          return name && name !== conflict.name
            ? [String(conflict.row), { action: "rename" as const, name }]
            : [String(conflict.row), { action: "reuse" as const, module_id: conflict.module_id }];
        })
      ),
      ...(allowDuplicate ? { allow_duplicate: true } : {}),
    };
    setIsSubmitting(true);
    try {
      await importService.startTodoist(workspaceSlug, projectId, file, preview.digest, config);
      await mutate();
      setFile(null);
      resetPreview();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Import queued",
        message: "Your tasks are being added in the background.",
      });
    } catch (error) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Could not start import", message: errorMessage(error) });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-8 pb-12">
      <section className="overflow-hidden rounded-xl border border-subtle bg-layer-1">
        <div className="bg-subtle grid gap-px md:grid-cols-3">
          {[
            ["1", "Destination", "Choose where the imported work belongs."],
            ["2", "Source file", "Select one Todoist CSV export."],
            ["3", "Review", "Confirm mappings before anything is created."],
          ].map(([number, title, description]) => (
            <div key={number} className="bg-layer-1 p-5">
              <div className="mb-3 flex size-7 items-center justify-center rounded-full bg-accent-primary text-11 font-semibold text-on-color">
                {number}
              </div>
              <h3 className="text-body-sm-medium text-primary">{title}</h3>
              <p className="mt-1 text-body-xs-regular text-secondary">{description}</p>
            </div>
          ))}
        </div>

        <div className="flex flex-col gap-5 p-5 md:p-6">
          <label className="flex flex-col gap-2 text-body-sm-medium text-primary">
            Destination project
            <CustomSelect
              value={projectId}
              onChange={(value: string) => {
                setProjectId(value);
                resetPreview();
              }}
              label={projectOptions.find((option) => option.value === projectId)?.label ?? "Select a project"}
              buttonClassName="w-full justify-between border border-subtle px-3 py-2.5 text-left"
            >
              {projectOptions.map((option) => (
                <CustomSelect.Option key={option.value} value={option.value}>
                  {option.label}
                </CustomSelect.Option>
              ))}
            </CustomSelect>
          </label>

          <label className="flex flex-col gap-2 text-body-sm-medium text-primary">
            CSV file
            <span className="flex min-h-24 cursor-pointer items-center gap-4 rounded-lg border border-dashed border-subtle bg-layer-2 px-4 py-5 transition-colors focus-within:border-accent-strong hover:border-strong">
              <FileText className="size-6 shrink-0 text-tertiary" />
              <span className="min-w-0">
                <span className="block truncate text-body-sm-medium text-primary">
                  {file?.name ?? "Choose a CSV export"}
                </span>
                <span className="mt-1 block text-body-xs-regular text-secondary">
                  Maximum size 5 MiB. The source is deleted after processing.
                </span>
              </span>
              <input
                className="sr-only"
                type="file"
                accept=".csv,text/csv"
                onChange={(event) => {
                  setFile(event.target.files?.[0] ?? null);
                  resetPreview();
                }}
              />
            </span>
          </label>

          {!preview && (
            <div>
              <Button
                variant="primary"
                size="lg"
                disabled={!projectId || !file || isSubmitting}
                onClick={handlePreview}
              >
                {isSubmitting ? "Reading file…" : "Preview import"}
              </Button>
            </div>
          )}
        </div>
      </section>

      {preview && (
        <section className="rounded-xl border border-subtle bg-layer-1 p-5 md:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-h5-medium text-primary">Import manifest</h3>
              <p className="mt-1 text-body-sm-regular text-secondary">
                Review the exact result before starting the background job.
              </p>
            </div>
            <span className="rounded-full bg-success-subtle px-3 py-1 text-body-xs-medium text-success-primary">
              File validated
            </span>
          </div>

          <dl className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              ["Tasks", preview.counts.task ?? 0],
              ["Sections", preview.counts.section ?? 0],
              ["Notes", preview.counts.note ?? 0],
              ["Warnings", preview.diagnostics.length],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-subtle bg-layer-2 p-3">
                <dt className="text-body-xs-medium text-secondary">{label}</dt>
                <dd className="mt-1 text-h4-semibold text-primary">{value}</dd>
              </div>
            ))}
          </dl>

          {(preview.enables_modules || preview.project_note_action === "skip") && (
            <div className="mt-5 flex gap-3 rounded-lg border border-subtle bg-layer-2 p-4 text-body-sm-regular text-secondary">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning-primary" />
              <div>
                {preview.enables_modules && <p>Sections will become modules and enable the Modules project feature.</p>}
                {preview.project_note_action === "skip" && (
                  <p>The project note will be skipped because the project already has a description.</p>
                )}
              </div>
            </div>
          )}

          {preview.assignees.length > 0 && (
            <div className="mt-6">
              <h4 className="text-body-sm-medium text-primary">Assignee mapping</h4>
              <p className="mt-1 text-body-xs-regular text-secondary">Unmapped identities remain unassigned.</p>
              <div className="mt-3 divide-y divide-subtle rounded-lg border border-subtle">
                {preview.assignees.map((sourceAssignee) => (
                  <div key={sourceAssignee} className="grid items-center gap-3 p-3 sm:grid-cols-2">
                    <span className="truncate text-body-sm-regular text-primary">{sourceAssignee}</span>
                    <select
                      className="rounded-md border border-subtle bg-surface-1 px-3 py-2 text-body-sm-regular text-primary outline-none focus:border-accent-strong"
                      value={assigneeMapping[sourceAssignee] ?? ""}
                      onChange={(event) =>
                        setAssigneeMapping((current) => ({ ...current, [sourceAssignee]: event.target.value }))
                      }
                    >
                      <option value="">Leave unassigned</option>
                      {(memberIds ?? []).map((memberId) => (
                        <option key={memberId} value={memberId}>
                          {projectMembers.getProjectMemberDetails(memberId, projectId ?? "")?.member.display_name ??
                            memberId}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>
          )}

          {preview.module_conflicts.length > 0 && (
            <div className="mt-6">
              <h4 className="text-body-sm-medium text-primary">Module-name conflicts</h4>
              <p className="mt-1 text-body-xs-regular text-secondary">
                Keep the original name to reuse the existing module, or enter a new name.
              </p>
              <div className="mt-3 space-y-3">
                {preview.module_conflicts.map((conflict) => (
                  <label key={conflict.row} className="flex flex-col gap-2 text-body-xs-medium text-secondary">
                    Section “{conflict.name}”
                    <input
                      className="rounded-md border border-subtle bg-surface-1 px-3 py-2 text-body-sm-regular text-primary outline-none focus:border-accent-strong"
                      value={renamedModules[conflict.row] ?? conflict.name}
                      onChange={(event) =>
                        setRenamedModules((current) => ({ ...current, [conflict.row]: event.target.value }))
                      }
                    />
                  </label>
                ))}
              </div>
            </div>
          )}

          {preview.duplicate && (
            <label className="mt-6 flex items-start gap-3 rounded-lg border border-warning-subtle bg-warning-subtle p-4 text-body-sm-regular text-primary">
              <input
                className="mt-0.5 size-4"
                type="checkbox"
                checked={allowDuplicate}
                onChange={(event) => setAllowDuplicate(event.target.checked)}
              />
              This exact file was already imported into this project. Import it again anyway.
            </label>
          )}

          <div className="mt-6 flex flex-wrap gap-3 border-t border-subtle pt-5">
            <Button
              variant="primary"
              size="lg"
              disabled={isSubmitting || (preview.duplicate && !allowDuplicate)}
              onClick={handleImport}
            >
              {isSubmitting ? "Starting import…" : "Start import"}
            </Button>
            <Button variant="secondary" size="lg" disabled={isSubmitting} onClick={resetPreview}>
              Choose another file
            </Button>
          </div>
        </section>
      )}

      <section>
        <div className="mb-3">
          <h3 className="text-h5-medium text-primary">Recent imports</h3>
          <p className="mt-1 text-body-sm-regular text-secondary">
            Background progress and row-level reports for this workspace.
          </p>
        </div>
        <div className="overflow-hidden rounded-xl border border-subtle bg-layer-1">
          {!jobs ? (
            <div className="flex items-center gap-2 p-5 text-body-sm-regular text-secondary">
              <Loader2 className="size-4 animate-spin" />
              Loading imports…
            </div>
          ) : jobs.results.length === 0 ? (
            <div className="p-6 text-body-sm-regular text-secondary">No imports have been started yet.</div>
          ) : (
            <div className="divide-y divide-subtle">
              {jobs.results.map((job) => (
                <div key={job.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex min-w-0 items-start gap-3">
                    {job.status === "completed" ? (
                      <CheckCircle2 className="mt-0.5 size-4 text-success-primary" />
                    ) : ACTIVE_STATUSES.has(job.status) ? (
                      <Loader2 className="mt-0.5 size-4 animate-spin text-accent-primary" />
                    ) : (
                      <AlertTriangle className="mt-0.5 size-4 text-warning-primary" />
                    )}
                    <div className="min-w-0">
                      <p className="truncate text-body-sm-medium text-primary">{job.project_detail.name}</p>
                      <p className="mt-0.5 text-body-xs-regular text-secondary capitalize">
                        {job.status} · {job.stats.imported_tasks ?? 0} of {job.stats.planned_tasks ?? 0} tasks
                      </p>
                    </div>
                  </div>
                  <a
                    className="text-body-xs-medium text-accent-primary hover:underline"
                    href={importService.reportUrl(workspaceSlug, job.id)}
                  >
                    Download report
                  </a>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
});
