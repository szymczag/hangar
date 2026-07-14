/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Loader, ToggleSwitch } from "@plane/ui";
// components
import { PageWrapper } from "@/components/common/page-wrapper";
// hooks
import { useInstance } from "@/hooks/store";
// types
import type { Route } from "./+types/page";
// local
import { InstanceEmailForm } from "./email-config-form";
import { EmailDeliveryLog } from "./email-delivery-log";

const InstanceEmailPage = observer(function InstanceEmailPage(_props: Route.ComponentProps) {
  // store
  const { fetchInstanceConfigurations, formattedConfig, disableEmail } = useInstance();

  const { isLoading } = useSWR("INSTANCE_CONFIGURATIONS", () => fetchInstanceConfigurations());

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSMTPEnabled, setIsSMTPEnabled] = useState(false);
  const isManagedDelivery =
    formattedConfig?.EMAIL_DELIVERY_V2_ENABLED === "1" && formattedConfig?.EMAIL_PROVIDER === "ses_api";

  const handleToggle = async () => {
    if (isSMTPEnabled) {
      setIsSubmitting(true);
      try {
        await disableEmail();
        setIsSMTPEnabled(false);
        setToast({
          title: "Email feature disabled",
          message: "Email feature has been disabled",
          type: TOAST_TYPE.SUCCESS,
        });
      } catch (_error) {
        setToast({
          title: "Error disabling email",
          message: "Failed to disable email feature. Please try again.",
          type: TOAST_TYPE.ERROR,
        });
      } finally {
        setIsSubmitting(false);
      }
      return;
    }
    setIsSMTPEnabled(true);
  };
  useEffect(() => {
    if (formattedConfig) {
      setIsSMTPEnabled(formattedConfig.ENABLE_SMTP === "1");
    }
  }, [formattedConfig]);

  return (
    <PageWrapper
      header={{
        title: "Email delivery",
        description: (
          <>
            Hangar records durable delivery receipts and can encrypt confidential notifications with OpenPGP.
            <div className="text-13 font-regular text-tertiary">
              Use a dedicated sending subdomain and monitor bounces, complaints, queue health, and sender reputation.
            </div>
          </>
        ),
        actions: isLoading ? (
          <Loader>
            <Loader.Item width="24px" height="16px" className="rounded-full" />
          </Loader>
        ) : isManagedDelivery ? (
          <span className="rounded-md border border-subtle bg-layer-2 px-2.5 py-1 text-11 font-medium text-secondary">
            Deployment managed
          </span>
        ) : (
          <ToggleSwitch value={isSMTPEnabled} onChange={handleToggle} size="sm" disabled={isSubmitting} />
        ),
      }}
    >
      <>
        {isManagedDelivery && !isLoading && formattedConfig && (
          <section className="max-w-4xl rounded-md border border-subtle bg-layer-2 p-5">
            <div className="text-13 font-medium text-primary">Amazon SES API delivery is active</div>
            <p className="mt-1 text-12 text-secondary">
              Credentials, region, feedback queue, cryptographic keys, and feature flags are controlled by the
              deployment. Change them in the Helm values and secret store, not in this browser.
            </p>
            <dl className="mt-4 grid gap-3 text-12 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <dt className="text-tertiary">Provider</dt>
                <dd className="mt-1 font-medium text-primary">SES API over HTTPS</dd>
              </div>
              <div>
                <dt className="text-tertiary">Region</dt>
                <dd className="font-mono mt-1 text-primary">{formattedConfig.EMAIL_SES_REGION}</dd>
              </div>
              <div>
                <dt className="text-tertiary">Sender</dt>
                <dd className="mt-1 text-primary">{formattedConfig.EMAIL_FROM || "Deployment default"}</dd>
              </div>
              <div>
                <dt className="text-tertiary">Confidential email</dt>
                <dd className="mt-1 font-medium text-primary">
                  {formattedConfig.EMAIL_OPENPGP_ENABLED === "1" ? "OpenPGP required" : "OpenPGP disabled"}
                </dd>
              </div>
            </dl>
          </section>
        )}
        {!isManagedDelivery && isSMTPEnabled && !isLoading && (
          <>
            {formattedConfig ? (
              <InstanceEmailForm config={formattedConfig} />
            ) : (
              <Loader className="space-y-10">
                <Loader.Item height="50px" width="75%" />
                <Loader.Item height="50px" width="75%" />
                <Loader.Item height="50px" width="40%" />
                <Loader.Item height="50px" width="40%" />
                <Loader.Item height="50px" width="20%" />
              </Loader>
            )}
          </>
        )}
        <EmailDeliveryLog />
      </>
    </PageWrapper>
  );
});

export const meta: Route.MetaFunction = () => [{ title: "Email Settings - God Mode" }];

export default InstanceEmailPage;
