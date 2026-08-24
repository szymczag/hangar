/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import useSWR from "swr";
// icons
import { UserCheck } from "lucide-react";
// plane internal packages
import { Loader } from "@plane/ui";
// components
import { AuthenticationMethodCard } from "@/components/authentication/authentication-method-card";
import { PageWrapper } from "@/components/common/page-wrapper";
// hooks
import { useInstance } from "@/hooks/store";
// types
import type { Route } from "./+types/page";
// local
import { InstanceIdentityImportForm } from "./form";

const InstanceIdentityImportPage = observer(function InstanceIdentityImportPage() {
  // store
  const { fetchInstanceConfigurations, formattedConfig } = useInstance();

  useSWR("INSTANCE_CONFIGURATIONS", () => fetchInstanceConfigurations());

  return (
    <PageWrapper
      customHeader={
        <AuthenticationMethodCard
          name="Identity import"
          description="Link existing accounts to the subjects your identity provider asserts, before you pin their domain."
          icon={<UserCheck className="h-6 w-6 p-0.5 text-tertiary" />}
          config={<></>}
          disabled={!formattedConfig}
          withBorder={false}
        />
      }
    >
      {formattedConfig ? (
        <InstanceIdentityImportForm config={formattedConfig} />
      ) : (
        <Loader className="space-y-8">
          <Loader.Item height="50px" width="25%" />
          <Loader.Item height="50px" />
          <Loader.Item height="50px" />
        </Loader>
      )}
    </PageWrapper>
  );
});

export const meta: Route.MetaFunction = () => [{ title: "Identity Import - God Mode" }];

export default InstanceIdentityImportPage;
