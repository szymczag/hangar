/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { observer } from "mobx-react";
import { Button } from "@makeplane/propel/components/button";
import { SelectField } from "@makeplane/propel/components/select-field";
import { TextButton } from "@makeplane/propel/components/text-button";
import { FileOutline } from "@makeplane/propel/icons";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import { useMember } from "@/hooks/store/use-member";
import { useProject } from "@/hooks/store/use-project";
import { importService } from "@/plane-web/services/import.service";
import type { TImportJob, TTodoistImportConfig, TTodoistImportPreview } from "@/plane-web/types/import";
import { TodoistImportHistory } from "./todoist-import-history";
import { TodoistImportReview, type TModuleAction } from "./todoist-import-review";

type Props = { workspaceSlug: string };

const errorMessage = (error: unknown, fallback: string): string => {
  if (typeof error !== "object" || error === null) return fallback;
  const payload = error as { error?: { message?: string } | string };
  return typeof payload.error === "string" ? payload.error : payload.error?.message || fallback;
};

export const TodoistImport = observer(function TodoistImport({ workspaceSlug }: Props) {
  const { t } = useTranslation();
  const [projectId, setProjectId] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<TTodoistImportPreview | null>(null);
  const [assigneeMapping, setAssigneeMapping] = useState<Record<string, string>>({});
  const [renamedModules, setRenamedModules] = useState<Record<number, string>>({});
  const [allowDuplicate, setAllowDuplicate] = useState(false);
  const [allowSkippedRows, setAllowSkippedRows] = useState(false);
  const [moduleActions, setModuleActions] = useState<Record<number, TModuleAction>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [historyRefreshToken, setHistoryRefreshToken] = useState(0);
  const [retryJobId, setRetryJobId] = useState<string | null>(null);
  const previewRequestId = useRef(0);
  const previewAbortController = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { workspaceProjectIds, getProjectById } = useProject();
  const { project: projectMembers } = useMember();
  const memberIds = projectId ? projectMembers.getProjectMemberIds(projectId, false) : null;

  useEffect(() => {
    if (projectId) void projectMembers.fetchProjectMembers(workspaceSlug, projectId);
  }, [projectId, projectMembers, workspaceSlug]);

  useEffect(() => () => previewAbortController.current?.abort(), []);

  const projectOptions = useMemo(
    () =>
      (workspaceProjectIds ?? []).map((id) => {
        const project = getProjectById(id);
        return { value: id, label: `${project?.identifier ?? ""} · ${project?.name ?? ""}` };
      }),
    [getProjectById, workspaceProjectIds]
  );
  const memberOptions = (memberIds ?? []).map((memberId) => ({
    value: memberId,
    label: projectMembers.getProjectMemberDetails(memberId, projectId ?? "")?.member.display_name ?? memberId,
  }));

  const resetPreview = () => {
    setPreview(null);
    setAssigneeMapping({});
    setRenamedModules({});
    setAllowDuplicate(false);
    setAllowSkippedRows(false);
    setModuleActions({});
    previewRequestId.current += 1;
    previewAbortController.current?.abort();
    setIsSubmitting(false);
  };

  const handlePreview = async () => {
    if (!projectId || !file) return;
    const requestId = ++previewRequestId.current;
    previewAbortController.current?.abort();
    const controller = new AbortController();
    previewAbortController.current = controller;
    setIsSubmitting(true);
    try {
      const result = await importService.previewTodoist(workspaceSlug, projectId, file, controller.signal);
      if (requestId !== previewRequestId.current) return;
      setPreview(result);
      setRenamedModules(Object.fromEntries(result.module_conflicts.map((conflict) => [conflict.row, conflict.name])));
      setModuleActions(Object.fromEntries(result.module_conflicts.map((conflict) => [conflict.row, "reuse"])));
    } catch (error) {
      if (controller.signal.aborted) return;
      setToast({
        type: "error",
        title: t("workspace_settings.settings.todoist_import.preview_error"),
        message: errorMessage(error, t("workspace_settings.settings.todoist_import.request_failed")),
      });
    } finally {
      if (requestId === previewRequestId.current) setIsSubmitting(false);
    }
  };

  const handleImport = async () => {
    if (!projectId || !file || !preview) return;
    const config: TTodoistImportConfig = {
      assignee_mapping: Object.fromEntries(Object.entries(assigneeMapping).filter(([, value]) => value)),
      module_conflicts: Object.fromEntries(
        preview.module_conflicts.map((conflict) => {
          const name = renamedModules[conflict.row]?.trim();
          return moduleActions[conflict.row] === "rename"
            ? [String(conflict.row), { action: "rename" as const, name: name ?? "" }]
            : [String(conflict.row), { action: "reuse" as const, module_id: conflict.module_id }];
        })
      ),
      ...(allowDuplicate ? { allow_duplicate: true } : {}),
      ...(allowSkippedRows ? { allow_skipped_rows: true } : {}),
    };
    setIsSubmitting(true);
    try {
      await importService.startTodoist(workspaceSlug, projectId, file, preview.preview_token, config, retryJobId);
      setHistoryRefreshToken((current) => current + 1);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      resetPreview();
      setRetryJobId(null);
      setToast({
        type: "success",
        title: t("workspace_settings.settings.todoist_import.queued_title"),
        message: t("workspace_settings.settings.todoist_import.queued_message"),
      });
    } catch (error) {
      setToast({
        type: "error",
        title: t("workspace_settings.settings.todoist_import.start_error"),
        message: errorMessage(error, t("workspace_settings.settings.todoist_import.request_failed")),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChooseAnother = () => {
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    resetPreview();
    setRetryJobId(null);
  };

  const handleRetry = (job: TImportJob) => {
    setProjectId(job.project);
    setRetryJobId(job.id);
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    resetPreview();
  };

  return (
    <div className="flex flex-col gap-8 pb-12">
      <section className="overflow-hidden rounded-lg border border-subtle bg-layer-1">
        <div className="bg-subtle grid gap-px md:grid-cols-3">
          {[
            [
              "1",
              t("workspace_settings.settings.todoist_import.steps.destination_title"),
              t("workspace_settings.settings.todoist_import.steps.destination_description"),
            ],
            [
              "2",
              t("workspace_settings.settings.todoist_import.steps.source_title"),
              t("workspace_settings.settings.todoist_import.steps.source_description"),
            ],
            [
              "3",
              t("workspace_settings.settings.todoist_import.steps.review_title"),
              t("workspace_settings.settings.todoist_import.steps.review_description"),
            ],
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
          <SelectField<string>
            label={t("workspace_settings.settings.todoist_import.destination_project")}
            size="lg"
            placeholder={t("workspace_settings.settings.todoist_import.select_project")}
            options={projectOptions}
            value={projectId}
            onValueChange={(value) => {
              if (!value) return;
              setProjectId(value);
              setRetryJobId(null);
              resetPreview();
            }}
          />

          {retryJobId && (
            <div className="rounded-lg border border-subtle bg-layer-2 p-3 text-body-xs-regular text-secondary">
              {t("workspace_settings.settings.todoist_import.retrying_job")} {retryJobId.slice(0, 8)}.{" "}
              {t("workspace_settings.settings.todoist_import.retry_help")}
              <span className="ml-2 inline-flex">
                <TextButton
                  variant="primary"
                  size="md"
                  label={t("workspace_settings.settings.todoist_import.cancel_retry")}
                  onClick={() => setRetryJobId(null)}
                />
              </span>
            </div>
          )}

          <label className="flex flex-col gap-2 text-body-sm-medium text-primary">
            {t("workspace_settings.settings.todoist_import.csv_file")}
            <span className="flex min-h-24 cursor-pointer items-center gap-4 rounded-lg border border-dashed border-subtle bg-layer-2 px-4 py-5 transition-colors focus-within:border-accent-strong hover:border-strong">
              <FileOutline className="size-6 shrink-0 text-tertiary" />
              <span className="min-w-0">
                <span className="block truncate text-body-sm-medium text-primary">
                  {file?.name ?? t("workspace_settings.settings.todoist_import.choose_csv")}
                </span>
                <span className="mt-1 block text-body-xs-regular text-secondary">
                  {t("workspace_settings.settings.todoist_import.file_help")}
                </span>
              </span>
              <input
                ref={fileInputRef}
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
                stretch="auto"
                disabled={!projectId || !file || isSubmitting}
                onClick={() => void handlePreview()}
                label={
                  isSubmitting
                    ? t("workspace_settings.settings.todoist_import.previewing")
                    : t("workspace_settings.settings.todoist_import.preview")
                }
              />
            </div>
          )}
        </div>
      </section>

      {preview && (
        <TodoistImportReview
          allowDuplicate={allowDuplicate}
          allowSkippedRows={allowSkippedRows}
          assigneeMapping={assigneeMapping}
          isSubmitting={isSubmitting}
          memberOptions={memberOptions}
          moduleActions={moduleActions}
          preview={preview}
          renamedModules={renamedModules}
          onAllowDuplicateChange={setAllowDuplicate}
          onAllowSkippedRowsChange={setAllowSkippedRows}
          onAssigneeChange={(sourceAssignee, memberId) =>
            setAssigneeMapping((current) => ({ ...current, [sourceAssignee]: memberId }))
          }
          onChooseAnother={handleChooseAnother}
          onImport={() => void handleImport()}
          onModuleActionChange={(row, action) => setModuleActions((current) => ({ ...current, [row]: action }))}
          onModuleNameChange={(row, name) => setRenamedModules((current) => ({ ...current, [row]: name }))}
        />
      )}

      <TodoistImportHistory
        workspaceSlug={workspaceSlug}
        errorMessage={(error) => errorMessage(error, t("workspace_settings.settings.todoist_import.request_failed"))}
        refreshToken={historyRefreshToken}
        onRetry={handleRetry}
      />
    </div>
  );
});
