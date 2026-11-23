/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import { Controller, useForm } from "react-hook-form";
import { ImageOutline } from "@makeplane/propel/icons";
// plane imports
import { E_PASSWORD_STRENGTH } from "@plane/constants";
import { Avatar } from "@makeplane/propel/components/avatar";
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { InputField } from "@makeplane/propel/components/input-field";
import { usePasswordStrength } from "@plane/blocks/auth";
import { setToast } from "@plane/blocks/toast";
import type { IUser } from "@plane/types";
import { EOnboardingSteps } from "@plane/types";
import { getFileURL, validatePersonName } from "@plane/utils";
// components
import { UserImageUploadModal } from "@/components/core/modals/user-image-upload-modal";
// helpers
import { isProfileManagedByProvider } from "@/helpers/provider-managed-profile";
// hooks
import { useInstance } from "@/hooks/store/use-instance";
import { useUser, useUserProfile } from "@/hooks/store/user";
// services
import { AuthService } from "@/services/auth.service";
// local components
import { CommonOnboardingHeader } from "../common";
import { MarketingConsent } from "./consent";
import { SetPasswordRoot } from "./set-password";

type Props = {
  handleStepChange: (step: EOnboardingSteps, skipInvites?: boolean) => void;
};

export type TProfileSetupFormValues = {
  first_name: string;
  last_name: string;
  avatar_url?: string | null;
  password?: string;
  confirm_password?: string;
  role?: string;
  use_case?: string[];
  has_marketing_email_consent?: boolean;
};

const authService = new AuthService();

const defaultValues: Partial<TProfileSetupFormValues> = {
  first_name: "",
  last_name: "",
  avatar_url: "",
  password: undefined,
  confirm_password: undefined,
  has_marketing_email_consent: true,
};

export const ProfileSetupStep = observer(function ProfileSetupStep({ handleStepChange }: Props) {
  // states
  const [isImageUploadModalOpen, setIsImageUploadModalOpen] = useState(false);
  // store hooks
  const { data: user, updateCurrentUser } = useUser();
  const { updateUserProfile } = useUserProfile();
  const { config: instanceConfig } = useInstance();
  // form info
  const {
    getValues,
    handleSubmit,
    control,
    watch,
    setValue,
    formState: { errors, isSubmitting, isValid },
  } = useForm<TProfileSetupFormValues>({
    defaultValues: {
      ...defaultValues,
      first_name: user?.first_name,
      last_name: user?.last_name,
      avatar_url: user?.avatar_url,
    },
    mode: "onChange",
  });
  // derived values
  const userAvatar = watch("avatar_url");

  const handleSetPassword = async (password: string) => {
    const token = await authService.requestCSRFToken().then((data) => data?.csrf_token);
    await authService.setPassword(token, { password });
  };

  const handleSubmitUserDetail = async (formData: TProfileSetupFormValues) => {
    const userDetailsPayload: Partial<IUser> = {
      first_name: formData.first_name,
      last_name: formData.last_name,
      avatar_url: formData.avatar_url ?? undefined,
    };
    try {
      await Promise.all([
        updateCurrentUser(userDetailsPayload),
        formData.password && handleSetPassword(formData.password),
      ]);
    } catch {
      setToast({
        type: "error",
        title: "Error",
        message: "User details update failed. Please try again!",
      });
    }
  };

  const onSubmit = async (formData: TProfileSetupFormValues) => {
    if (!user) return;
    updateUserProfile({
      has_marketing_email_consent: formData.has_marketing_email_consent,
    });
    await handleSubmitUserDetail(formData);
    handleStepChange(EOnboardingSteps.PROFILE_SETUP);
  };

  const handleDelete = (url: string | null | undefined) => {
    if (!url) return;
    setValue("avatar_url", "");
  };

  // derived values
  const isPasswordAlreadySetup = !user?.is_password_autoset;
  // Offering to set a password an instance will not accept is an invitation to
  // waste time: where password sign-in is off, the only way in is the provider.
  // An account bound to an identity provider has no Hangar password and the API
  // refuses to set one, so the step is not offered to it either.
  const canSignInWithPassword = instanceConfig?.is_email_password_enabled !== false && !user?.is_federated;
  // The provider overwrites these on every sign-in when attribute sync is on,
  // so editing them here would be undone by the next login without explanation.
  // Shared with profile settings, which asks the same question of the same two
  // values and must not drift from this one.
  const providerManagingProfile = isProfileManagedByProvider(instanceConfig, user);
  const currentPassword = watch("password") || undefined;
  const currentConfirmPassword = watch("confirm_password") || undefined;
  const passwordStrength = usePasswordStrength(currentPassword ?? "");

  const isValidPassword = useMemo(() => {
    if (currentPassword) {
      if (
        currentPassword === currentConfirmPassword &&
        passwordStrength.strength === E_PASSWORD_STRENGTH.STRENGTH_VALID
      ) {
        return true;
      } else {
        return false;
      }
    } else {
      return true;
    }
  }, [currentPassword, currentConfirmPassword, passwordStrength.strength]);

  // Check for all available fields validation and if password field is available, then checks for password validation (strength + confirmation).
  // Also handles the condition for optional password i.e if password field is optional it only checks for above validation if it's not empty.
  const showPasswordSetup = !isPasswordAlreadySetup && canSignInWithPassword;
  const isButtonDisabled = isSubmitting || !isValid || (showPasswordSetup && !isValidPassword);

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-10">
      {/* Header */}
      <CommonOnboardingHeader title="Create your profile." description="This is how you will appear in Hangar." />

      {/* Profile Picture Section */}
      <Controller
        control={control}
        name="avatar_url"
        render={({ field: { onChange, value } }) => (
          <UserImageUploadModal
            isOpen={isImageUploadModalOpen}
            onClose={() => setIsImageUploadModalOpen(false)}
            handleRemove={async () => handleDelete(getValues("avatar_url"))}
            onSuccess={(url) => {
              onChange(url);
              setIsImageUploadModalOpen(false);
            }}
            value={value && value.trim() !== "" ? value : null}
          />
        )}
      />
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-3">
          <button
            className="flex rounded-full"
            type="button"
            onClick={() => setIsImageUploadModalOpen(true)}
            aria-label={userAvatar ? "Change image" : "Upload image"}
            disabled={providerManagingProfile}
          >
            <Avatar
              size="2xl"
              src={userAvatar ? getFileURL(userAvatar) : undefined}
              alt={user?.display_name}
              fallback={watch("first_name")?.[0]?.toUpperCase() || undefined}
            />
          </button>
          <input type="file" className="hidden" id="profile-image-input" />
          {/* Hidden rather than disabled when the provider owns it: sync deletes
              an uploaded avatar outright, so offering the control at all would be
              offering to lose the file. */}
          {!providerManagingProfile && (
            <Button
              type="button"
              variant="ghost"
              size="lg"
              stretch="auto"
              onClick={() => setIsImageUploadModalOpen(true)}
              icon={<Icon icon={ImageOutline} />}
              iconPosition="start"
              label={userAvatar ? "Change image" : "Upload image"}
            />
          )}
        </div>
        <div className="flex w-full flex-col gap-6">
          {/* Name Input */}
          <Controller
            control={control}
            name="first_name"
            rules={{
              required: "Name is required",
              validate: validatePersonName,
              maxLength: {
                value: 50,
                message: "Name must be within 50 characters.",
              },
            }}
            render={({ field: { value, onChange, ref } }) => (
              <InputField
                ref={ref}
                id="first_name"
                name="first_name"
                size="xl"
                orientation="vertical"
                type="text"
                label="Name"
                required
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder="Enter your full name"
                autoComplete="on"
                readOnly={providerManagingProfile}
                disabled={providerManagingProfile}
                hint={
                  providerManagingProfile
                    ? `Managed by ${user?.last_login_medium}. Your name and picture are taken from there on every sign-in, so a change made here would not survive the next one — change them with your provider instead.`
                    : undefined
                }
                error={errors.first_name?.message}
              />
            )}
          />

          {/* setting up password for the first time */}
          {showPasswordSetup && (
            <SetPasswordRoot
              onPasswordChange={(password) => setValue("password", password)}
              onConfirmPasswordChange={(confirm_password) => setValue("confirm_password", confirm_password)}
            />
          )}
        </div>
        {/* Continue Button */}
        <Button variant="primary" type="submit" stretch="full" size="lg" disabled={isButtonDisabled} label="Continue" />
      </div>

      {/* Marketing Consent */}
      {!instanceConfig?.is_self_managed && (
        <MarketingConsent
          isChecked={!!watch("has_marketing_email_consent")}
          handleChange={(has_marketing_email_consent) =>
            setValue("has_marketing_email_consent", has_marketing_email_consent)
          }
        />
      )}
    </form>
  );
});
