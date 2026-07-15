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
  const {
    fetchEmailDeliveryConfiguration,
    fetchInstanceConfigurations,
    formattedConfig,
    disableEmail,
    emailDeliveryConfiguration,
  } = useInstance();

  const { isLoading: isConfigurationLoading } = useSWR("INSTANCE_CONFIGURATIONS", () => fetchInstanceConfigurations());
  const { isLoading: isEmailDeliveryLoading } = useSWR("INSTANCE_EMAIL_DELIVERY", () =>
    fetchEmailDeliveryConfiguration()
  );

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSMTPEnabled, setIsSMTPEnabled] = useState(false);
  const isLoading = isConfigurationLoading || isEmailDeliveryLoading;
  const isManagedDelivery = emailDeliveryConfiguration?.is_deployment_managed === true;

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
        {isManagedDelivery && !isLoading && emailDeliveryConfiguration?.ses && (
          <section className="max-w-4xl rounded-md border border-subtle bg-layer-2 p-5">
            <div className="text-13 font-medium text-primary">Amazon SES API delivery is active</div>
            <p className="mt-1 text-12 text-secondary">
              These are the effective deployment settings. Change them only through your .env file, Helm values, and
              deployment secret store; this browser cannot edit Amazon SES delivery.
            </p>
            <dl className="mt-4 grid gap-3 text-12 sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <dt className="text-tertiary">Provider</dt>
                <dd className="mt-1 font-medium text-primary">SES API over HTTPS</dd>
              </div>
              <div>
                <dt className="text-tertiary">Region</dt>
                <dd className="font-mono mt-1 text-primary">
                  {emailDeliveryConfiguration.ses.region || "Not configured"}
                </dd>
              </div>
              <div>
                <dt className="text-tertiary">Sender</dt>
                <dd className="mt-1 text-primary">{emailDeliveryConfiguration.sender || "Not configured"}</dd>
              </div>
              <div>
                <dt className="text-tertiary">Reply-to</dt>
                <dd className="mt-1 text-primary">{emailDeliveryConfiguration.reply_to || "Not configured"}</dd>
              </div>
              <div>
                <dt className="text-tertiary">AWS account ID</dt>
                <dd className="font-mono mt-1 text-primary">
                  {emailDeliveryConfiguration.ses.account_id || "Not configured"}
                </dd>
              </div>
              <div>
                <dt className="text-tertiary">AWS access key ID</dt>
                <dd className="font-mono mt-1 text-primary">
                  {emailDeliveryConfiguration.ses.access_key_id || "Workload identity or default provider chain"}
                </dd>
              </div>
              <div>
                <dt className="text-tertiary">Authentication configuration set</dt>
                <dd className="font-mono mt-1 text-primary">
                  {emailDeliveryConfiguration.ses.auth_configuration_set || "Not configured"}
                </dd>
              </div>
              <div>
                <dt className="text-tertiary">Notification configuration set</dt>
                <dd className="font-mono mt-1 text-primary">
                  {emailDeliveryConfiguration.ses.notification_configuration_set || "Not configured"}
                </dd>
              </div>
              <div>
                <dt className="text-tertiary">Feedback SNS topic</dt>
                <dd className="font-mono mt-1 break-all text-primary">
                  {emailDeliveryConfiguration.ses.events_topic_arn || "Not configured"}
                </dd>
              </div>
              <div>
                <dt className="text-tertiary">Feedback SQS queue</dt>
                <dd className="font-mono mt-1 break-all text-primary">
                  {emailDeliveryConfiguration.ses.events_queue_url || "Not configured"}
                </dd>
              </div>
              <div>
                <dt className="text-tertiary">Durable delivery</dt>
                <dd className="mt-1 font-medium text-primary">
                  {emailDeliveryConfiguration.durable_delivery_enabled ? "Enabled" : "Disabled"}
                </dd>
              </div>
              <div>
                <dt className="text-tertiary">OpenPGP for user profiles</dt>
                <dd className="mt-1 font-medium text-primary">
                  {emailDeliveryConfiguration.openpgp_enabled ? "Available in Profile → Security" : "Disabled"}
                </dd>
              </div>
            </dl>
          </section>
        )}
        {!isManagedDelivery && emailDeliveryConfiguration && isSMTPEnabled && !isLoading && (
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
