/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
// Hangar imports
import { Button } from "@makeplane/propel/components/button";
import { CheckboxField } from "@makeplane/propel/components/checkbox-field";
import {
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogHeading,
  DialogMain,
  DialogTitle,
} from "@makeplane/propel/components/dialog";
import { InputField } from "@makeplane/propel/components/input-field";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { IProject } from "@plane/types";
import { projectIdentifierSanitizer } from "@plane/utils";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useAppRouter } from "@/hooks/use-app-router";

type TDuplicateProjectModalProps = {
  isOpen: boolean;
  // Only what the form seeds from, so the sidebar's partial project works here
  // as well as the full record the project card and settings page hold.
  project: Pick<IProject, "id" | "name" | "identifier">;
  onClose: () => void;
};

type TFormValues = {
  name: string;
  identifier: string;
  labels: boolean;
  estimates: boolean;
  intake: boolean;
  members: boolean;
  cycles: boolean;
  modules: boolean;
  views: boolean;
  work_items: boolean;
};

/**
 * Options the API also defaults on. Anything that grants access or carries
 * someone else's work stays off until it is asked for.
 */
const OPTIONAL_COPY_FIELDS = [
  { key: "labels", labelKey: "labels" },
  { key: "estimates", labelKey: "common.estimates" },
  { key: "intake", labelKey: "intake" },
  { key: "members", labelKey: "members" },
  { key: "cycles", labelKey: "cycles" },
  { key: "modules", labelKey: "modules" },
  { key: "views", labelKey: "views" },
  { key: "work_items", labelKey: "work_items" },
] as const;

export function DuplicateProjectModal(props: TDuplicateProjectModalProps) {
  const { isOpen, project, onClose } = props;
  // store hooks
  const { duplicateProject } = useProject();
  // router
  const router = useAppRouter();
  const { workspaceSlug } = useParams();
  // translation
  const { t } = useTranslation();
  // form info
  const {
    control,
    formState: { errors, isSubmitting },
    handleSubmit,
    reset,
    setError,
  } = useForm<TFormValues>();

  // Seed from the source every time the modal opens, so reopening it after a
  // failed submit does not keep a stale name the API already rejected.
  useEffect(() => {
    if (!isOpen) return;
    reset({
      name: `${project.name} (Copy)`,
      identifier: projectIdentifierSanitizer(project.identifier ?? "").slice(0, 9),
      labels: true,
      estimates: true,
      intake: true,
      members: false,
      cycles: false,
      modules: false,
      views: false,
      work_items: false,
    });
  }, [isOpen, project.name, project.identifier, reset]);

  const onSubmit = async (values: TFormValues) => {
    if (!workspaceSlug) return;

    try {
      const copy = await duplicateProject(workspaceSlug.toString(), project.id, {
        name: values.name.trim(),
        identifier: values.identifier.trim().toUpperCase(),
        include: {
          labels: values.labels,
          estimates: values.estimates,
          intake: values.intake,
          members: values.members,
          cycles: values.cycles,
          modules: values.modules,
          views: values.views,
          work_items: values.work_items,
        },
      });

      onClose();
      setToast({
        type: "success",
        title: t("success"),
        message: t("project_duplicated_successfully"),
      });
      router.push(`/${workspaceSlug}/projects/${copy.id}/issues`);
    } catch (error) {
      // The endpoint answers in two shapes, and only one of them was decoded
      // here before: the service raises `{ error: CODE }`, but a serializer
      // rejection is DRF's field map, `{ name: [CODE] }`. A validation failure
      // therefore fell through to the generic toast with nothing said about the
      // field that caused it.
      const body = (error as { data?: Record<string, unknown> })?.data ?? {};
      const fieldCodes = (field: string): string[] => {
        const value = body[field];
        return Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === "string") : [];
      };
      const code = typeof body.error === "string" ? body.error : undefined;
      const has = (field: string, wanted: string) => code === wanted || fieldCodes(field).includes(wanted);

      if (has("name", "PROJECT_NAME_ALREADY_EXIST")) {
        setError("name", { message: t("project_name_already_taken") });
        return;
      }
      if (has("identifier", "PROJECT_IDENTIFIER_ALREADY_EXIST")) {
        setError("identifier", { message: t("project_identifier_already_taken") });
        return;
      }
      if (has("name", "PROJECT_NAME_CANNOT_CONTAIN_SPECIAL_CHARACTERS")) {
        setError("name", { message: t("project_name_cannot_contain_special_characters") });
        return;
      }
      if (has("identifier", "PROJECT_IDENTIFIER_CANNOT_CONTAIN_SPECIAL_CHARACTERS")) {
        setError("identifier", { message: t("project_identifier_cannot_contain_special_characters") });
        return;
      }

      setToast({
        type: "error",
        title: t("error"),
        message:
          code === "PROJECT_TOO_LARGE_TO_COPY_SYNCHRONOUSLY"
            ? t("project_too_large_to_copy")
            : t("couldnt_duplicate_the_project"),
      });
    }
  };

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent size="md">
        <form onSubmit={handleSubmit(onSubmit)} className="flex min-h-0 flex-1 flex-col">
          <DialogMain>
            <DialogHeader>
              <DialogHeading>
                <DialogTitle>{t("duplicate_project")}</DialogTitle>
                <DialogDescription>{t("duplicate_project_description")}</DialogDescription>
              </DialogHeading>
            </DialogHeader>
            <DialogBody>
              <div className="flex flex-col gap-6">
                <div className="flex gap-4">
                  <div className="min-w-0 flex-grow">
                    <Controller
                      control={control}
                      name="name"
                      rules={{ required: true, maxLength: 255 }}
                      render={({ field: { value, onChange, ref } }) => (
                        <InputField
                          id="duplicate-project-name"
                          size="lg"
                          orientation="vertical"
                          label={t("project_name")}
                          type="text"
                          value={value}
                          onChange={onChange}
                          ref={ref}
                          error={errors.name?.message || (errors.name ? true : undefined)}
                          autoComplete="off"
                        />
                      )}
                    />
                  </div>
                  <div className="w-28 flex-shrink-0">
                    <Controller
                      control={control}
                      name="identifier"
                      rules={{ required: true, maxLength: 12 }}
                      render={({ field: { value, onChange, ref } }) => (
                        <InputField
                          id="duplicate-project-identifier"
                          size="lg"
                          orientation="vertical"
                          label={t("project_id")}
                          type="text"
                          value={value}
                          // Mirrors the create form: uppercase, no separators, capped.
                          onChange={(event) =>
                            onChange(projectIdentifierSanitizer(event.target.value.toUpperCase()).slice(0, 12))
                          }
                          ref={ref}
                          error={errors.identifier?.message || (errors.identifier ? true : undefined)}
                          autoComplete="off"
                        />
                      )}
                    />
                  </div>
                </div>

                <div>
                  <p className="text-body-sm-medium text-primary">{t("duplicate_project_what_to_copy")}</p>
                  <p className="mt-1 text-body-xs-regular text-secondary">{t("duplicate_project_always_copied")}</p>
                  <div className="mt-3 grid grid-cols-2 gap-y-2.5">
                    {OPTIONAL_COPY_FIELDS.map((option) => (
                      <Controller
                        key={option.key}
                        control={control}
                        name={option.key}
                        render={({ field: { value, onChange } }) => (
                          <CheckboxField
                            size="md"
                            label={t(option.labelKey)}
                            checked={!!value}
                            onCheckedChange={(checked) => onChange(checked)}
                          />
                        )}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </DialogBody>
          </DialogMain>
          <DialogActions>
            <Button variant="secondary" size="md" stretch="auto" label={t("cancel")} onClick={onClose} />
            <Button
              variant="primary"
              size="md"
              stretch="auto"
              type="submit"
              loading={isSubmitting}
              label={isSubmitting ? t("duplicating_project") : t("duplicate_project")}
            />
          </DialogActions>
        </form>
      </DialogContent>
    </Dialog>
  );
}
