/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { EmptyStateCompact } from "@plane/propel/empty-state";
import { APITokenService } from "@plane/services";
// components
import { CreateApiTokenModal } from "@/components/api-token/modal/create-token-modal";
import { ApiTokenListItem } from "@/components/api-token/token-list-item";
import { ProfileSettingsHeading } from "@/components/settings/profile/heading";
import { APITokenSettingsLoader } from "@/components/ui/loader/settings/api-token";
// helpers
import { workspacesAllowingApiTokens } from "@/helpers/api-token-eligibility";
// hooks
import { useInstance } from "@/hooks/store/use-instance";
import { useWorkspace } from "@/hooks/store/use-workspace";
// constants
import { API_TOKENS_LIST } from "@plane/constants";

const apiTokenService = new APITokenService();

export const APITokensProfileSettings = observer(function APITokensProfileSettings() {
  // states
  const [isCreateTokenModalOpen, setIsCreateTokenModalOpen] = useState(false);
  // store hooks
  const { data: tokens } = useSWR(API_TOKENS_LIST, () => apiTokenService.list());
  const { workspaces } = useWorkspace();
  const { config } = useInstance();
  // translation
  const { t } = useTranslation();

  // A token names the workspace it acts in, and minting one needs a sufficient
  // role there. With no such workspace the answer is already no, so the offer is
  // withdrawn rather than left to fail on submit — existing tokens stay listed
  // and revocable, which is the part that still matters to someone in that
  // position.
  const eligibleWorkspaces = workspacesAllowingApiTokens(workspaces, config?.api_token_minimum_role);
  const canCreateToken = eligibleWorkspaces.length > 0;

  if (!tokens) {
    return <APITokenSettingsLoader />;
  }

  return (
    <div className="size-full">
      <CreateApiTokenModal isOpen={isCreateTokenModalOpen} onClose={() => setIsCreateTokenModalOpen(false)} />
      <ProfileSettingsHeading
        title={t("account_settings.api_tokens.title")}
        description={t("account_settings.api_tokens.description")}
        control={
          canCreateToken ? (
            <Button variant="primary" size="lg" onClick={() => setIsCreateTokenModalOpen(true)}>
              {t("workspace_settings.settings.api_tokens.add_token")}
            </Button>
          ) : (
            <span className="max-w-sm text-11 text-tertiary">
              Creating a token needs a sufficient role in the workspace it would act in, and none of yours grants it. An
              instance administrator sets the required role.
            </span>
          )
        }
      />
      <div className="mt-7">
        {tokens.length > 0 ? (
          <>
            <div>
              {tokens.map((token) => (
                <ApiTokenListItem key={token.id} token={token} />
              ))}
            </div>
          </>
        ) : (
          <EmptyStateCompact
            assetKey="token"
            assetClassName="size-20"
            title={t("settings_empty_state.tokens.title")}
            description={t("settings_empty_state.tokens.description")}
            actions={
              canCreateToken
                ? [
                    {
                      label: t("settings_empty_state.tokens.cta_primary"),
                      onClick: () => {
                        setIsCreateTokenModalOpen(true);
                      },
                    },
                  ]
                : []
            }
            align="start"
            rootClassName="py-20"
          />
        )}
      </div>
    </div>
  );
});
