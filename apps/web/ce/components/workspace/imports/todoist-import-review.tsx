/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Badge } from "@makeplane/propel/components/badge";
import { Button } from "@makeplane/propel/components/button";
import { CheckboxField } from "@makeplane/propel/components/checkbox-field";
import { InputField } from "@makeplane/propel/components/input-field";
import { SelectField } from "@makeplane/propel/components/select-field";
import { WarningTriangleOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
import type { TTodoistImportPreview } from "@/plane-web/types/import";

export type TModuleAction = "reuse" | "rename";

type TMemberOption = {
  label: string;
  value: string;
};

type Props = {
  allowDuplicate: boolean;
  allowSkippedRows: boolean;
  assigneeMapping: Record<string, string>;
  isSubmitting: boolean;
  memberOptions: TMemberOption[];
  moduleActions: Record<number, TModuleAction>;
  preview: TTodoistImportPreview;
  renamedModules: Record<number, string>;
  onAllowDuplicateChange: (value: boolean) => void;
  onAllowSkippedRowsChange: (value: boolean) => void;
  onAssigneeChange: (sourceAssignee: string, memberId: string) => void;
  onChooseAnother: () => void;
  onImport: () => void;
  onModuleActionChange: (row: number, action: TModuleAction) => void;
  onModuleNameChange: (row: number, name: string) => void;
};

export function TodoistImportReview({
  allowDuplicate,
  allowSkippedRows,
  assigneeMapping,
  isSubmitting,
  memberOptions,
  moduleActions,
  preview,
  renamedModules,
  onAllowDuplicateChange,
  onAllowSkippedRowsChange,
  onAssigneeChange,
  onChooseAnother,
  onImport,
  onModuleActionChange,
  onModuleNameChange,
}: Props) {
  const { t } = useTranslation();
  const errors = preview.diagnostics.filter((item) => item.level === "error");
  const warnings = preview.diagnostics.filter((item) => item.level === "warning");
  const hasErrors = errors.length > 0;
  const hasInvalidModuleRename = preview.module_conflicts.some(
    (conflict) => moduleActions[conflict.row] === "rename" && !renamedModules[conflict.row]?.trim()
  );

  return (
    <section className="rounded-lg border border-subtle bg-layer-1 p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-h5-medium text-primary">
            {t("workspace_settings.settings.todoist_import.manifest_title")}
          </h3>
          <p className="mt-1 text-body-sm-regular text-secondary">
            {t("workspace_settings.settings.todoist_import.manifest_description")}
          </p>
        </div>
        <Badge
          variant={hasErrors ? "danger" : "success"}
          size="md"
          label={
            hasErrors
              ? t("workspace_settings.settings.todoist_import.validated_with_skips")
              : t("workspace_settings.settings.todoist_import.validated")
          }
        />
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-5">
        {[
          [t("workspace_settings.settings.todoist_import.tasks"), preview.counts.task ?? 0],
          [t("workspace_settings.settings.todoist_import.sections"), preview.counts.section ?? 0],
          [t("workspace_settings.settings.todoist_import.notes"), preview.counts.note ?? 0],
          [t("workspace_settings.settings.todoist_import.errors"), errors.length],
          [t("workspace_settings.settings.todoist_import.warnings"), warnings.length],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-subtle bg-layer-2 p-3">
            <dt className="text-body-xs-medium text-secondary">{label}</dt>
            <dd className="mt-1 text-h4-semibold text-primary">{value}</dd>
          </div>
        ))}
      </dl>

      {preview.diagnostics.length > 0 && (
        <div className="mt-5 overflow-hidden rounded-lg border border-subtle">
          <div className="border-b border-subtle bg-layer-2 px-4 py-2 text-body-xs-medium text-secondary">
            {t("workspace_settings.settings.todoist_import.diagnostics")}
          </div>
          <ul className="max-h-64 divide-y divide-subtle overflow-y-auto">
            {preview.diagnostics.map((diagnostic) => (
              <li
                key={`${diagnostic.code}-${diagnostic.row ?? "file"}-${diagnostic.field ?? "none"}-${diagnostic.level}`}
                className="flex gap-3 px-4 py-3"
              >
                <WarningTriangleOutline
                  className={`mt-0.5 size-4 shrink-0 ${
                    diagnostic.level === "error" ? "text-danger-primary" : "text-warning-primary"
                  }`}
                />
                <div>
                  <p className="text-body-sm-regular text-primary">{diagnostic.message}</p>
                  <p className="mt-0.5 text-body-xs-regular text-secondary">
                    {diagnostic.row
                      ? `${t("workspace_settings.settings.todoist_import.row")} ${diagnostic.row}`
                      : t("workspace_settings.settings.todoist_import.file")}{" "}
                    · {diagnostic.code}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {(preview.enables_modules || preview.project_note_action === "skip") && (
        <div className="mt-5 flex gap-3 rounded-lg border border-subtle bg-layer-2 p-4 text-body-sm-regular text-secondary">
          <WarningTriangleOutline className="mt-0.5 size-4 shrink-0 text-warning-primary" />
          <div>
            {preview.enables_modules && <p>{t("workspace_settings.settings.todoist_import.modules_notice")}</p>}
            {preview.project_note_action === "skip" && (
              <p>{t("workspace_settings.settings.todoist_import.project_note_notice")}</p>
            )}
          </div>
        </div>
      )}

      {preview.assignees.length > 0 && (
        <div className="mt-6">
          <h4 className="text-body-sm-medium text-primary">
            {t("workspace_settings.settings.todoist_import.assignee_mapping")}
          </h4>
          <p className="mt-1 text-body-xs-regular text-secondary">
            {t("workspace_settings.settings.todoist_import.assignee_help")}
          </p>
          <div className="mt-3 divide-y divide-subtle rounded-lg border border-subtle">
            {preview.assignees.map((sourceAssignee) => (
              <div key={sourceAssignee} className="grid items-center gap-3 p-3 sm:grid-cols-2">
                <span className="truncate text-body-sm-regular text-primary">{sourceAssignee}</span>
                <SelectField<string>
                  aria-label={`${t("workspace_settings.settings.todoist_import.assignee_mapping")}: ${sourceAssignee}`}
                  size="lg"
                  options={[
                    { value: "", label: t("workspace_settings.settings.todoist_import.leave_unassigned") },
                    ...memberOptions,
                  ]}
                  value={assigneeMapping[sourceAssignee] ?? ""}
                  onValueChange={(memberId) => onAssigneeChange(sourceAssignee, memberId ?? "")}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {preview.module_conflicts.length > 0 && (
        <div className="mt-6">
          <h4 className="text-body-sm-medium text-primary">
            {t("workspace_settings.settings.todoist_import.module_conflicts")}
          </h4>
          <p className="mt-1 text-body-xs-regular text-secondary">
            {t("workspace_settings.settings.todoist_import.module_conflicts_help")}
          </p>
          <div className="mt-3 space-y-3">
            {preview.module_conflicts.map((conflict) => (
              <div key={conflict.row} className="rounded-lg border border-subtle p-3">
                <p className="text-body-xs-medium text-secondary">
                  {t("workspace_settings.settings.todoist_import.section")} “{conflict.name}”
                </p>
                <div className="mt-2 flex flex-col gap-2">
                  <SelectField<TModuleAction>
                    aria-label={`${t("workspace_settings.settings.todoist_import.module_conflicts")}: ${conflict.name}`}
                    size="lg"
                    options={[
                      { value: "reuse", label: t("workspace_settings.settings.todoist_import.reuse_module") },
                      { value: "rename", label: t("workspace_settings.settings.todoist_import.rename_module") },
                    ]}
                    value={moduleActions[conflict.row] ?? "reuse"}
                    onValueChange={(action) => {
                      if (action) onModuleActionChange(conflict.row, action);
                    }}
                  />
                  <InputField
                    aria-label={`${t("workspace_settings.settings.todoist_import.rename_module")}: ${conflict.name}`}
                    size="lg"
                    orientation="vertical"
                    value={renamedModules[conflict.row] ?? conflict.name}
                    disabled={moduleActions[conflict.row] !== "rename"}
                    onChange={(event) => onModuleNameChange(conflict.row, event.target.value)}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {hasErrors && (
        <div className="mt-6 rounded-lg border border-danger-subtle bg-danger-subtle p-4">
          <CheckboxField
            name="allow-skipped-rows"
            size="lg"
            label={t("workspace_settings.settings.todoist_import.skip_confirmation")}
            checked={allowSkippedRows}
            onCheckedChange={(checked) => onAllowSkippedRowsChange(checked)}
          />
        </div>
      )}

      {preview.duplicate && (
        <div className="mt-6 rounded-lg border border-warning-subtle bg-warning-subtle p-4">
          <CheckboxField
            name="allow-duplicate"
            size="lg"
            label={t("workspace_settings.settings.todoist_import.duplicate_confirmation")}
            checked={allowDuplicate}
            onCheckedChange={(checked) => onAllowDuplicateChange(checked)}
          />
        </div>
      )}

      <div className="mt-6 flex flex-wrap gap-3 border-t border-subtle pt-5">
        <Button
          variant="primary"
          size="lg"
          stretch="auto"
          disabled={
            isSubmitting ||
            (preview.duplicate && !allowDuplicate) ||
            (hasErrors && !allowSkippedRows) ||
            hasInvalidModuleRename
          }
          onClick={onImport}
          label={
            isSubmitting
              ? t("workspace_settings.settings.todoist_import.starting")
              : t("workspace_settings.settings.todoist_import.start")
          }
        />
        <Button
          variant="secondary"
          size="lg"
          stretch="auto"
          disabled={isSubmitting}
          onClick={onChooseAnother}
          label={t("workspace_settings.settings.todoist_import.choose_another")}
        />
      </div>
    </section>
  );
}
