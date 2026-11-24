/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { ShieldCheck } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
// components
import { FormContainer } from "@/components/account/auth-forms/common/container";
import { SetPasswordForm } from "@/components/account/auth-forms/set-password";
import { AuthHeaderBase } from "@/components/auth-screens/header";
// helpers
import { EPageTypes } from "@/helpers/authentication.helper";
// hooks
import { useInstance } from "@/hooks/store/use-instance";
import { useUser } from "@/hooks/store/user";
// layouts
import DefaultLayout from "@/layouts/default-layout";
import { AuthenticationWrapper } from "@/lib/wrappers/authentication-wrapper";

function NoPasswordNotice({ title, description }: { title: string; description: string }) {
  return (
    <FormContainer>
      <div className="flex gap-3 rounded-md border border-subtle-1 bg-layer-2 p-4 text-13">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-secondary" />
        <div>
          <p className="font-medium text-primary">{title}</p>
          <p className="mt-1 leading-5 text-secondary">{description}</p>
        </div>
      </div>
    </FormContainer>
  );
}

// Fork (see FORK.md): upstream renders the reset-password form here, which
// needs the uidb64 and token of a reset email and, without them, posts to
// /auth/reset-password/undefined/undefined/. This page is for a signed-in
// account that has no password of its own yet (the SET_PASSWORD gate sends any
// other to the security settings), so it uses the session-bound set-password
// form, and does not offer a password the API would refuse.
const SetPasswordContent = observer(function SetPasswordContent() {
  const { data: currentUser } = useUser();
  const { config: instanceConfig } = useInstance();

  // An account bound to an identity provider has no Hangar password, and the
  // API answers 403 PASSWORD_MANAGED_BY_IDENTITY_PROVIDER to set-password.
  if (currentUser?.is_federated)
    return (
      <NoPasswordNotice
        title="This account signs in through an identity provider"
        description="It has no Hangar password and cannot be given one. Your password, and anything else guarding the account such as a second factor, are managed where you sign in."
      />
    );

  // Same rule as onboarding: a password the instance will not accept at
  // sign-in is not worth setting.
  if (instanceConfig?.is_email_password_enabled === false)
    return (
      <NoPasswordNotice
        title="Password sign-in is switched off"
        description="This instance does not accept passwords at sign-in, so there is no password to set. Sign in the way your administrator has set up."
      />
    );

  return <SetPasswordForm />;
});

function SetPasswordPage() {
  const { t } = useTranslation();
  // The visitor is already signed in here, so the header offers no
  // "New to Hangar? Sign up" or "Sign in" switch, only the logo.
  return (
    <DefaultLayout>
      <AuthenticationWrapper pageType={EPageTypes.SET_PASSWORD}>
        <div className="relative z-10 flex h-screen w-screen flex-col items-center overflow-hidden overflow-y-auto px-8 pt-6 pb-10">
          <AuthHeaderBase pageTitle={t("auth.set_password.title")} />
          <SetPasswordContent />
        </div>
      </AuthenticationWrapper>
    </DefaultLayout>
  );
}

export default SetPasswordPage;
