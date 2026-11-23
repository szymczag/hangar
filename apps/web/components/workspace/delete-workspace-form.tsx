/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// Hangar Imports
import { useTranslation } from "@plane/i18n";
import { TypeToConfirmDialog } from "@plane/blocks/dialog";
import { setToast } from "@plane/blocks/toast";
import type { IWorkspace } from "@plane/types";
// hooks
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUserSettings } from "@/hooks/store/user";
import { useAppRouter } from "@/hooks/use-app-router";

/**
 * The second phrase Hangar has always asked for, on top of the workspace's name.
 * Deleting a workspace takes every project, page and member with it, so the
 * dialog keeps both checks rather than upstream's name alone.
 */
export const DELETE_WORKSPACE_CONFIRM_PHRASE = "delete my workspace";

type Props = {
  data: IWorkspace | null;
  isOpen: boolean;
  onClose: () => void;
};

export const DeleteWorkspaceForm = observer(function DeleteWorkspaceForm(props: Props) {
  const { data, isOpen, onClose } = props;
  // router
  const router = useAppRouter();
  // store hooks
  const { deleteWorkspace } = useWorkspace();
  const { t } = useTranslation();
  const { getWorkspaceRedirectionUrl } = useWorkspace();
  const { fetchCurrentUserSettings } = useUserSettings();

  const onSubmit = async () => {
    if (!data) return;

    try {
      await deleteWorkspace(data.slug);
      await fetchCurrentUserSettings();
      onClose();
      router.push(getWorkspaceRedirectionUrl());
      setToast({
        type: "success",
        title: t("workspace_settings.settings.general.delete_modal.success_title"),
        message: t("workspace_settings.settings.general.delete_modal.success_message"),
      });
    } catch (_error) {
      setToast({
        type: "error",
        title: t("workspace_settings.settings.general.delete_modal.error_title"),
        message: t("workspace_settings.settings.general.delete_modal.error_message"),
      });
    }
  };

  return (
    <TypeToConfirmDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onSubmit}
      title={t("workspace_settings.settings.general.delete_modal.title")}
      description={t("workspace_settings.settings.general.delete_modal.confirm_description", {
        workspaceName: data?.name ?? "",
      })}
      fields={[
        {
          name: "workspaceName",
          label: t("workspace_settings.settings.members.leave_input_label"),
          expectedValue: data?.name ?? "",
        },
        {
          name: "confirmDelete",
          label: t("workspace_settings.settings.general.delete_modal.confirm_phrase_label", {
            phrase: DELETE_WORKSPACE_CONFIRM_PHRASE,
          }),
          expectedValue: DELETE_WORKSPACE_CONFIRM_PHRASE,
        },
      ]}
      confirmLabel={t("confirm")}
      loadingLabel={t("deleting")}
    />
  );
});
