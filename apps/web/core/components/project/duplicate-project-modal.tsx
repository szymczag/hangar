/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import { CopyPlus } from "lucide-react";
// Hangar imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IProject } from "@plane/types";
import { Checkbox, Input, EModalPosition, EModalWidth, ModalCore } from "@plane/ui";
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
        },
      });

      onClose();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("success"),
        message: t("project_duplicated_successfully"),
      });
      router.push(`/${workspaceSlug}/projects/${copy.id}/issues`);
    } catch (error) {
      // `duplicateProject` rejects with the response, so the API's error codes
      // are on `.data.error` -- the same shape the create form decodes.
      const code = (error as { data?: { error?: string } })?.data?.error;

      if (code === "PROJECT_NAME_ALREADY_EXIST") {
        setError("name", { message: t("project_name_already_taken") });
        return;
      }
      if (code === "PROJECT_IDENTIFIER_ALREADY_EXIST") {
        setError("identifier", { message: t("project_identifier_already_taken") });
        return;
      }

      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("error"),
        message:
          code === "PROJECT_TOO_LARGE_TO_COPY_SYNCHRONOUSLY"
            ? t("project_too_large_to_copy")
            : t("couldnt_duplicate_the_project"),
      });
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.CENTER} width={EModalWidth.XXL}>
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6 p-6">
        <div className="flex w-full items-center justify-start gap-4">
          <span className="place-items-center rounded-full bg-layer-1 p-3">
            <CopyPlus className="h-5 w-5 text-secondary" aria-hidden="true" />
          </span>
          <h3 className="text-18 font-medium 2xl:text-20">{t("duplicate_project")}</h3>
        </div>

        <p className="text-13 leading-6 text-secondary">{t("duplicate_project_description")}</p>

        <div className="flex gap-4">
          <div className="flex-grow">
            <label htmlFor="duplicate-project-name" className="text-13 text-secondary">
              {t("project_name")}
            </label>
            <Controller
              control={control}
              name="name"
              rules={{ required: true, maxLength: 255 }}
              render={({ field: { value, onChange, ref } }) => (
                <Input
                  id="duplicate-project-name"
                  type="text"
                  value={value}
                  onChange={onChange}
                  ref={ref}
                  hasError={Boolean(errors.name)}
                  className="mt-1 w-full"
                  autoComplete="off"
                />
              )}
            />
            {errors.name?.message && <p className="mt-1 text-11 text-danger-primary">{errors.name.message}</p>}
          </div>

          <div className="w-28 flex-shrink-0">
            <label htmlFor="duplicate-project-identifier" className="text-13 text-secondary">
              {t("project_id")}
            </label>
            <Controller
              control={control}
              name="identifier"
              rules={{ required: true, maxLength: 12 }}
              render={({ field: { value, onChange, ref } }) => (
                <Input
                  id="duplicate-project-identifier"
                  type="text"
                  value={value}
                  // Mirrors the create form: uppercase, no separators, capped.
                  onChange={(event) =>
                    onChange(projectIdentifierSanitizer(event.target.value.toUpperCase()).slice(0, 12))
                  }
                  ref={ref}
                  hasError={Boolean(errors.identifier)}
                  className="mt-1 w-full"
                  autoComplete="off"
                />
              )}
            />
            {errors.identifier?.message && (
              <p className="mt-1 text-11 text-danger-primary">{errors.identifier.message}</p>
            )}
          </div>
        </div>

        <div>
          <p className="text-13 font-medium text-primary">{t("duplicate_project_what_to_copy")}</p>
          <p className="mt-1 text-11 text-secondary">{t("duplicate_project_always_copied")}</p>
          <div className="mt-3 grid grid-cols-2 gap-y-2.5">
            {OPTIONAL_COPY_FIELDS.map((option) => (
              <Controller
                key={option.key}
                control={control}
                name={option.key}
                render={({ field: { value, onChange } }) => (
                  <label className="flex cursor-pointer items-center gap-2 text-13 text-secondary">
                    <Checkbox checked={!!value} onChange={(event) => onChange(event.target.checked)} />
                    <span>{t(option.labelKey)}</span>
                  </label>
                )}
              />
            ))}
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="lg" onClick={onClose}>
            {t("cancel")}
          </Button>
          <Button variant="primary" size="lg" type="submit" loading={isSubmitting}>
            {isSubmitting ? t("duplicating_project") : t("duplicate_project")}
          </Button>
        </div>
      </form>
    </ModalCore>
  );
}
