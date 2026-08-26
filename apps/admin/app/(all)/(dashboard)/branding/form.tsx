/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Trash2 } from "lucide-react";
// plane internal packages
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { AuthService, InstanceBrandingService } from "@plane/services";
import type { TBrandingImage } from "@plane/services";
import type { IFormattedInstanceConfiguration, TInstanceBrandingConfigurationKeys } from "@plane/types";
// components
import { CodeBlock } from "@/components/common/code-block";
import type { TControllerInputFormField } from "@/components/common/controller-input";
import { ControllerInput } from "@/components/common/controller-input";
// helpers
import { configurationErrorMessage } from "@/helpers/configuration-error";
// hooks
import { useInstance } from "@/hooks/store";
import { useConfigurationEditable } from "@/hooks/use-configuration-editable";

const authService = new AuthService();
const brandingService = new InstanceBrandingService();

type Props = {
  config: IFormattedInstanceConfiguration;
};

type BrandingFormValues = Record<TInstanceBrandingConfigurationKeys, string> & {
  INSTANCE_ACCENT_COLOR: string;
  INSTANCE_LOGIN_BACKDROP_COLOR: string;
};

type ImageFieldProps = {
  label: string;
  hint: string;
  emptyLabel: string;
  url: string;
  onUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onClear: () => void;
  disabled: boolean;
};

function ImageField(props: ImageFieldProps) {
  const { label, hint, emptyLabel, url, onUpload, onClear, disabled } = props;
  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium text-primary">{label}</span>
      <div className="flex items-center gap-4">
        <div className="flex h-14 w-44 items-center justify-center overflow-hidden rounded-md border border-strong bg-surface-1">
          {url ? (
            <img src={url} alt={label} className="max-h-full max-w-full object-contain" />
          ) : (
            <span className="text-11 text-tertiary">{emptyLabel}</span>
          )}
        </div>
        <div className="flex flex-col gap-2">
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            className="text-sm"
            onChange={onUpload}
            disabled={disabled}
          />
          {url && (
            <Button variant="secondary" size="sm" onClick={onClear} disabled={disabled}>
              <Trash2 className="h-3.5 w-3.5" /> Remove
            </Button>
          )}
        </div>
      </div>
      <span className="text-11 text-tertiary">
        {hint} Served to anyone who opens the sign-in page, so it is validated as an image server-side rather than
        trusted from the upload.
      </span>
    </div>
  );
}

export function InstanceBrandingForm(props: Props) {
  const { config } = props;
  // states
  const [csrfToken, setCsrfToken] = useState<string | undefined>(undefined);
  const [images, setImages] = useState<Record<TBrandingImage, string>>({
    logo: config.INSTANCE_LOGO_ASSET_ID ? `/api/assets/v2/static/${config.INSTANCE_LOGO_ASSET_ID}/` : "",
    "login-background": config.INSTANCE_LOGIN_BACKGROUND_ASSET_ID
      ? `/api/assets/v2/static/${config.INSTANCE_LOGIN_BACKGROUND_ASSET_ID}/`
      : "",
  });
  const [isUploading, setIsUploading] = useState(false);
  const [isLicenseNoticeDirty, setIsLicenseNoticeDirty] = useState(false);
  // store hooks
  const { updateInstanceConfigurations } = useInstance();
  const isConfigurationEditable = useConfigurationEditable();
  // form
  const {
    handleSubmit,
    control,
    reset,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<BrandingFormValues>({
    defaultValues: {
      INSTANCE_BRANDING_NAME: config.INSTANCE_BRANDING_NAME ?? "",
      INSTANCE_SIGN_IN_HEADER: config.INSTANCE_SIGN_IN_HEADER ?? "",
      INSTANCE_SIGN_IN_SUBHEADER: config.INSTANCE_SIGN_IN_SUBHEADER ?? "",
      INSTANCE_ACCENT_COLOR: config.INSTANCE_ACCENT_COLOR ?? "",
      INSTANCE_LOGIN_BACKDROP_COLOR: config.INSTANCE_LOGIN_BACKDROP_COLOR ?? "",
    },
  });
  const [showLicenseNotice, setShowLicenseNotice] = useState(config.INSTANCE_SHOW_LICENSE_NOTICE !== "0");

  useEffect(() => {
    authService.requestCSRFToken().then((data) => data?.csrf_token && setCsrfToken(data.csrf_token));
  }, []);

  const BRANDING_FIELDS: TControllerInputFormField<BrandingFormValues>[] = [
    {
      key: "INSTANCE_BRANDING_NAME",
      type: "text",
      label: "Organisation name",
      description: (
        <>Shown in the sign-in page footer and in the browser tab. Left empty, neither mentions an organisation.</>
      ),
      placeholder: "Your organisation",
      error: Boolean(errors.INSTANCE_BRANDING_NAME),
      required: false,
    },
    {
      key: "INSTANCE_SIGN_IN_HEADER",
      type: "text",
      label: "Sign-in headline",
      description: <>Replaces &quot;Work in all dimensions.&quot; Left empty, that wording stays.</>,
      placeholder: "Work in all dimensions.",
      error: Boolean(errors.INSTANCE_SIGN_IN_HEADER),
      required: false,
    },
    {
      key: "INSTANCE_ACCENT_COLOR",
      type: "text",
      label: "Accent colour",
      description: (
        <>
          Hex, such as <CodeBlock darkerShade>#1d4ed8</CodeBlock>. Colours the sign-in button, links and focus outlines.
          Empty keeps the default.
        </>
      ),
      placeholder: "#1d4ed8",
      error: Boolean(errors.INSTANCE_ACCENT_COLOR),
      required: false,
    },
    {
      key: "INSTANCE_LOGIN_BACKDROP_COLOR",
      type: "text",
      label: "Sign-in backdrop colour",
      description: <>Hex. Shown behind the form, and behind the background image where it does not cover.</>,
      placeholder: "#0b1220",
      error: Boolean(errors.INSTANCE_LOGIN_BACKDROP_COLOR),
      required: false,
    },
    {
      key: "INSTANCE_SIGN_IN_SUBHEADER",
      type: "text",
      label: "Sign-in subheading",
      description: <>Replaces &quot;Welcome back to Hangar.&quot; Left empty, that wording stays.</>,
      placeholder: "Welcome back to Hangar.",
      error: Boolean(errors.INSTANCE_SIGN_IN_SUBHEADER),
      required: false,
    },
  ];

  const onSubmit = async (formData: BrandingFormValues) => {
    try {
      const response = await updateInstanceConfigurations({
        ...formData,
        INSTANCE_SHOW_LICENSE_NOTICE: showLicenseNotice ? "1" : "0",
      });
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Saved", message: "Branding updated." });
      reset({
        INSTANCE_BRANDING_NAME: response.find((item) => item.key === "INSTANCE_BRANDING_NAME")?.value ?? "",
        INSTANCE_SIGN_IN_HEADER: response.find((item) => item.key === "INSTANCE_SIGN_IN_HEADER")?.value ?? "",
        INSTANCE_SIGN_IN_SUBHEADER: response.find((item) => item.key === "INSTANCE_SIGN_IN_SUBHEADER")?.value ?? "",
        INSTANCE_ACCENT_COLOR: response.find((item) => item.key === "INSTANCE_ACCENT_COLOR")?.value ?? "",
        INSTANCE_LOGIN_BACKDROP_COLOR:
          response.find((item) => item.key === "INSTANCE_LOGIN_BACKDROP_COLOR")?.value ?? "",
      });
    } catch (error) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: configurationErrorMessage(error) });
    }
  };

  const uploadImage = async (kind: TBrandingImage, event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !csrfToken) return;
    setIsUploading(true);
    try {
      const result = await brandingService.uploadImage(csrfToken, kind, file);
      setImages((previous) => ({ ...previous, [kind]: result.asset_url }));
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Image updated", message: "The sign-in page now shows it." });
    } catch (error) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Image not updated", message: configurationErrorMessage(error) });
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  };

  const clearImage = async (kind: TBrandingImage) => {
    if (!csrfToken) return;
    setIsUploading(true);
    try {
      await brandingService.clearImage(csrfToken, kind);
      setImages((previous) => ({ ...previous, [kind]: "" }));
    } catch (error) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Image not cleared", message: configurationErrorMessage(error) });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="flex max-w-4xl flex-col gap-8">
      <ImageField
        label="Logo"
        hint="Replaces the Hangar wordmark on the sign-in page and in this panel."
        emptyLabel="Hangar wordmark"
        url={images.logo}
        onUpload={(event) => uploadImage("logo", event)}
        onClear={() => clearImage("logo")}
        disabled={isUploading || !isConfigurationEditable}
      />

      <ImageField
        label="Sign-in background"
        hint="Fills the page behind the sign-in form. Anything readable behind text works best; a busy photograph does not."
        emptyLabel="No background"
        url={images["login-background"]}
        onUpload={(event) => uploadImage("login-background", event)}
        onClear={() => clearImage("login-background")}
        disabled={isUploading || !isConfigurationEditable}
      />

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-8">
        <div className="grid grid-cols-1 gap-x-16 gap-y-8 lg:grid-cols-2">
          {BRANDING_FIELDS.map((field) => (
            <ControllerInput
              key={field.key}
              control={control}
              type={field.type}
              name={field.key}
              label={field.label}
              description={field.description}
              placeholder={field.placeholder}
              error={field.error}
              required={field.required}
            />
          ))}
        </div>
        <div>
          <Button
            variant="primary"
            onClick={handleSubmit(onSubmit)}
            loading={isSubmitting}
            disabled={(!isDirty && !isLicenseNoticeDirty) || isSubmitting || !isConfigurationEditable}
          >
            {isSubmitting ? "Saving" : "Save changes"}
          </Button>
        </div>
      </form>

      <div className="flex flex-col gap-2 rounded-md border border-subtle p-4 text-13">
        <label className="flex items-start gap-3" htmlFor="show-license-notice">
          <input
            id="show-license-notice"
            type="checkbox"
            aria-label="Show the licence notice on the sign-in page"
            className="mt-1"
            checked={showLicenseNotice}
            onChange={(event) => {
              setShowLicenseNotice(event.target.checked);
              setIsLicenseNoticeDirty(true);
            }}
            disabled={!isConfigurationEditable}
          />
          <span>
            <span className="font-medium text-secondary">Show the licence notice on the sign-in page</span>
            <span className="block text-11 text-tertiary">
              Hangar is AGPL-3.0. Section 13 requires that people using it over a network be offered its source, so
              turning this off moves the offer rather than removing it: the link stays in the in-app help menu, where
              every signed-in person reaches it. That link is not configurable, deliberately.
            </span>
          </span>
        </label>
      </div>
    </div>
  );
}
