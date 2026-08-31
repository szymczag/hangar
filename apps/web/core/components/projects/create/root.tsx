/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { FormProvider, useForm } from "react-hook-form";
// plane imports
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { EFileAssetType } from "@plane/types";
// components
import ProjectCommonAttributes from "@/components/project/create/common-attributes";
import ProjectCreateHeader from "@/components/project/create/header";
import ProjectCreateButtons from "@/components/project/create/project-create-buttons";
// hooks
import { getCoverImageType, uploadCoverImage } from "@/helpers/cover-image.helper";
import { useProject } from "@/hooks/store/use-project";
import { usePlatformOS } from "@/hooks/use-platform-os";
// plane web types
import type { TProject } from "@plane/types";
import { ProjectAttributes } from "./attributes";
import { getProjectFormValues } from "./utils";

export type TCreateProjectFormProps = {
  setToFavorite?: boolean;
  workspaceSlug: string;
  onClose: () => void;
  handleNextStep: (projectId: string) => void;
  data?: Partial<TProject>;
  templateId?: string;
  handleTemplateSelect?: () => void;
  updateCoverImageStatus: (projectId: string, coverImage: string) => Promise<void>;
};

export const CreateProjectForm = observer(function CreateProjectForm(props: TCreateProjectFormProps) {
  const {
    setToFavorite,
    workspaceSlug,
    data,
    onClose,
    handleNextStep,
    updateCoverImageStatus,
    templateId,
    handleTemplateSelect,
  } = props;
  // store
  const { t } = useTranslation();
  const { addProjectToFavorites, createProject, duplicateProject, updateProject, getProjectById } = useProject();
  // states
  const [shouldAutoSyncIdentifier, setShouldAutoSyncIdentifier] = useState(true);
  // form info
  const methods = useForm<TProject>({
    defaultValues: { ...getProjectFormValues(), ...data },
    reValidateMode: "onChange",
  });
  const { handleSubmit, reset, setValue } = methods;
  const sourceProject = templateId ? getProjectById(templateId) : undefined;

  // Seeding from a source is a one-way door within a single open: the person
  // picked a project to start from, so its settings become the starting point.
  useEffect(() => {
    if (!sourceProject) return;
    reset({
      ...getProjectFormValues(),
      ...sourceProject,
      id: undefined,
      name: `${sourceProject.name} (Copy)`,
      identifier: "",
    });
  }, [sourceProject, reset]);
  const { isMobile } = usePlatformOS();
  const handleAddToFavorites = (projectId: string) => {
    if (!workspaceSlug) return;

    addProjectToFavorites(workspaceSlug.toString(), projectId).catch(() => {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("toast.error"),
        message: t("failed_to_remove_project_from_favorites"),
      });
    });
  };

  /**
   * Copies a cover that is bundled with the app into the workspace's storage and
   * attaches it to the project.
   *
   * Deliberately called only once the project exists. An asset is stored against
   * the record it belongs to, and the identifier of a project that has not been
   * created yet is the empty string, which the API refuses — so uploading first
   * could never have worked. The bundled covers cannot simply be recorded by URL
   * instead: they are hashed build assets, and the name changes with every
   * release.
   */
  const attachBundledCover = async (projectId: string, coverImage: string) => {
    const uploadedAssetUrl = await uploadCoverImage(coverImage, {
      workspaceSlug: workspaceSlug.toString(),
      entityIdentifier: projectId,
      entityType: EFileAssetType.PROJECT_COVER,
      isUserAsset: false,
    });
    await updateCoverImageStatus(projectId, uploadedAssetUrl);
    await updateProject(workspaceSlug.toString(), projectId, { cover_image_url: uploadedAssetUrl });
  };

  const onSubmit = async (formData: Partial<TProject>) => {
    // Upper case identifier
    formData.identifier = formData.identifier?.toUpperCase();
    const coverImage = formData.cover_image_url;
    const isBundledCover = Boolean(coverImage) && getCoverImageType(coverImage!) === "local_static";

    // An address the browser can fetch is recorded as it stands; only a bundled
    // cover has to be copied into storage, and that waits for the project.
    if (coverImage && !isBundledCover) {
      formData.cover_image = coverImage;
      formData.cover_image_asset = null;
    }

    // With a source chosen, the server copies its configuration rather than
    // creating an empty project; it also owns the cover, so the bundled-cover
    // path below stays out of the way unless the person changed it here.
    const creation = templateId
      ? duplicateProject(workspaceSlug.toString(), templateId, {
          name: formData.name ?? undefined,
          identifier: formData.identifier ?? undefined,
          network: formData.network ?? undefined,
        })
      : createProject(workspaceSlug.toString(), formData);

    return creation
      .then(async (res) => {
        if (coverImage && isBundledCover && !templateId) {
          // The project exists by now, so a cover that cannot be stored costs
          // the cover and nothing else. Failing the whole creation here would
          // discard everything the person filled in over a decorative image.
          try {
            await attachBundledCover(res.id, coverImage);
          } catch (error) {
            console.error("Error uploading cover image:", error);
            setToast({
              type: TOAST_TYPE.WARNING,
              title: t("warning"),
              message:
                error instanceof Error && error.message
                  ? error.message
                  : "The project was created, but its cover image could not be stored.",
            });
          }
        } else if (coverImage && coverImage.startsWith("http")) {
          await updateCoverImageStatus(res.id, coverImage);
          await updateProject(workspaceSlug.toString(), res.id, { cover_image_url: coverImage });
        }
        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: t("success"),
          message: templateId ? t("project_duplicated_successfully") : t("project_created_successfully"),
        });

        if (setToFavorite) {
          handleAddToFavorites(res.id);
        }
        return handleNextStep(res.id);
      })
      .catch((err) => {
        try {
          // Handle the new error format where codes are nested in arrays under field names
          const errorData = err?.data ?? {};

          const nameError = errorData.name?.includes("PROJECT_NAME_ALREADY_EXIST");
          const identifierError = errorData?.identifier?.includes("PROJECT_IDENTIFIER_ALREADY_EXIST");
          const nameSpecialCharError = errorData?.name?.includes("PROJECT_NAME_CANNOT_CONTAIN_SPECIAL_CHARACTERS");

          if (nameError || identifierError || nameSpecialCharError) {
            if (nameError) {
              setToast({
                type: TOAST_TYPE.ERROR,
                title: t("toast.error"),
                message: t("project_name_already_taken"),
              });
            }

            if (identifierError) {
              setToast({
                type: TOAST_TYPE.ERROR,
                title: t("toast.error"),
                message: t("project_identifier_already_taken"),
              });
            }

            if (nameSpecialCharError) {
              setToast({
                type: TOAST_TYPE.ERROR,
                title: t("toast.error"),
                message: t("project_name_cannot_contain_special_characters"),
              });
            }
          } else {
            setToast({
              type: TOAST_TYPE.ERROR,
              title: t("toast.error"),
              message: t("something_went_wrong"),
            });
          }
        } catch (error) {
          // Fallback error handling if the error processing fails
          console.error("Error processing API error:", error);
          setToast({
            type: TOAST_TYPE.ERROR,
            title: t("toast.error"),
            message: t("something_went_wrong"),
          });
        }
      });
  };

  const handleClose = () => {
    onClose();
    setShouldAutoSyncIdentifier(true);
    setTimeout(() => {
      reset();
    }, 300);
  };

  return (
    <FormProvider {...methods}>
      <ProjectCreateHeader handleClose={handleClose} isMobile={isMobile} handleTemplateSelect={handleTemplateSelect} />

      <form onSubmit={handleSubmit(onSubmit)} className="px-3">
        <div className="mt-9 space-y-6 pb-5">
          <ProjectCommonAttributes
            setValue={setValue}
            isMobile={isMobile}
            shouldAutoSyncIdentifier={shouldAutoSyncIdentifier}
            setShouldAutoSyncIdentifier={setShouldAutoSyncIdentifier}
          />
          <ProjectAttributes isMobile={isMobile} />
        </div>
        <ProjectCreateButtons handleClose={handleClose} />
      </form>
    </FormProvider>
  );
});
