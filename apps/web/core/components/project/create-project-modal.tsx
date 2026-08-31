/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { EModalPosition, EModalWidth, ModalCore } from "@plane/ui";
import { getAssetIdFromUrl, checkURLValidity } from "@plane/utils";
// plane ui
// helpers
// hooks
import useKeypress from "@/hooks/use-keypress";
// plane web components
import { CreateProjectForm } from "@/components/projects/create/root";
// plane web types
import type { TProject } from "@plane/types";
// services
import { FileService } from "@/services/file.service";
const fileService = new FileService();
import { ProjectSourcePicker } from "@/components/project/create/source-picker";
import { ProjectFeatureUpdate } from "./project-feature-update";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  setToFavorite?: boolean;
  workspaceSlug: string;
  data?: Partial<TProject>;
  templateId?: string;
};

enum EProjectCreationSteps {
  SOURCE_SELECTION = "SOURCE_SELECTION",
  CREATE_PROJECT = "CREATE_PROJECT",
  FEATURE_SELECTION = "FEATURE_SELECTION",
}

export function CreateProjectModal(props: Props) {
  const { isOpen, onClose, setToFavorite = false, workspaceSlug, data, templateId } = props;
  // states
  const [currentStep, setCurrentStep] = useState<EProjectCreationSteps>(EProjectCreationSteps.CREATE_PROJECT);
  const [createdProjectId, setCreatedProjectId] = useState<string | null>(null);
  // The project this one is being started from, if any. `templateId` from props
  // wins, so a caller can open the modal already pointed at a source.
  const [sourceProjectId, setSourceProjectId] = useState<string | undefined>(templateId);

  useEffect(() => {
    if (isOpen) {
      setCurrentStep(EProjectCreationSteps.CREATE_PROJECT);
      setCreatedProjectId(null);
      setSourceProjectId(templateId);
    }
  }, [isOpen, templateId]);

  const handleNextStep = (projectId: string) => {
    if (!projectId) return;
    setCreatedProjectId(projectId);
    setCurrentStep(EProjectCreationSteps.FEATURE_SELECTION);
  };

  const handleCoverImageStatusUpdate = async (projectId: string, coverImage: string) => {
    if (!checkURLValidity(coverImage)) {
      await fileService.updateBulkProjectAssetsUploadStatus(workspaceSlug, projectId, projectId, {
        asset_ids: [getAssetIdFromUrl(coverImage)],
      });
    }
  };

  useKeypress("Escape", () => {
    if (isOpen) onClose();
  });

  return (
    <ModalCore isOpen={isOpen} position={EModalPosition.TOP} width={EModalWidth.XXXXL}>
      {currentStep === EProjectCreationSteps.SOURCE_SELECTION && (
        <ProjectSourcePicker
          onSelect={(projectId) => {
            setSourceProjectId(projectId);
            setCurrentStep(EProjectCreationSteps.CREATE_PROJECT);
          }}
          onCancel={() => setCurrentStep(EProjectCreationSteps.CREATE_PROJECT)}
        />
      )}
      {currentStep === EProjectCreationSteps.CREATE_PROJECT && (
        <CreateProjectForm
          setToFavorite={setToFavorite}
          workspaceSlug={workspaceSlug}
          onClose={onClose}
          updateCoverImageStatus={handleCoverImageStatusUpdate}
          handleNextStep={handleNextStep}
          data={data}
          templateId={sourceProjectId}
          handleTemplateSelect={() => setCurrentStep(EProjectCreationSteps.SOURCE_SELECTION)}
        />
      )}
      {currentStep === EProjectCreationSteps.FEATURE_SELECTION && (
        <ProjectFeatureUpdate projectId={createdProjectId} workspaceSlug={workspaceSlug} onClose={onClose} />
      )}
    </ModalCore>
  );
}
