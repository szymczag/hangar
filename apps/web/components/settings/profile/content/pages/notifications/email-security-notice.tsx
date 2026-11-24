/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { Banner } from "@makeplane/propel/components/banner";
import { Button } from "@makeplane/propel/components/button";
// hooks
import { useCommandPalette } from "@/hooks/store/use-command-palette";
import { useAppRouter } from "@/hooks/use-app-router";
// services
import { UserService } from "@/services/user.service";

const userService = new UserService();
// Shares the security tab's cache entry, so verifying a key there clears this
// notice without a refetch.
const STATUS_KEY = "CURRENT_USER_EMAIL_SECURITY";

type NoticeCopy = {
  title: string;
  body: string;
  action: string | null;
};

/**
 * The toggles below this notice only ever govern email. When the instance
 * requires OpenPGP and the account has no verified key, every one of them is
 * inert: `resolve_mail_policy` suppresses project notifications outright rather
 * than sending a cleartext copy, and the message stays in Hangar. Saying so
 * here is the only place the person finds out before waiting for mail that
 * never arrives.
 */
export const EmailSecurityNotice = observer(function EmailSecurityNotice() {
  const router = useAppRouter();
  const { profileSettingsModal, toggleProfileSettingsModal } = useCommandPalette();
  const { data } = useSWR(STATUS_KEY, () => userService.getEmailSecurityStatus(), {
    errorRetryCount: 0,
  });

  // Absent until the status resolves, and on an instance that never enabled
  // encrypted delivery there is nothing to warn about: notifications are sent.
  if (!data || !data.enabled) return null;

  const isSuppressed = data.active_suppressions.length > 0;
  if (data.active_key && !isSuppressed) return null;

  const copy: NoticeCopy = data.active_key
    ? {
        title: "Email delivery to your address is paused",
        body:
          "A provider recorded a permanent bounce or a complaint for your address, so Hangar stopped sending to it. " +
          "These preferences are saved, but no email is sent until an instance administrator reviews and lifts the pause. " +
          "Notifications remain available in Hangar.",
        action: null,
      }
    : data.pending_key
      ? {
          title: "Verify your key or these notifications will not be sent",
          body:
            "Your OpenPGP key is uploaded but not verified yet, and this instance sends project notifications only to a " +
            "verified key. Until you enter the code from the encrypted challenge message, everything below is saved but " +
            "produces no email — the notifications stay in Hangar instead.",
          action: "Finish verification",
        }
      : {
          title: "Add and verify an OpenPGP key or these notifications will not be sent",
          body:
            "This instance sends project notifications only to a verified OpenPGP key, and your account has none. " +
            "Everything below is saved, but it produces no email until a key is verified — the notifications stay in " +
            "Hangar instead. Account access and recovery messages are unaffected.",
          action: "Set up encrypted email",
        };

  // These settings render both inside the profile modal and on the
  // /settings/profile/:tab route, which move between tabs differently. Pushing
  // the route while the modal is open would navigate the page behind it.
  const openSecurityTab = () => {
    if (profileSettingsModal.isOpen) {
      toggleProfileSettingsModal({ activeTab: "security" });
      return;
    }
    router.push("/settings/profile/security");
  };

  // A danger banner is announced as an alert, as this notice always was.
  return (
    <div className="mb-7 max-w-3xl">
      <Banner
        variant="danger"
        placement="inline"
        title={copy.title}
        description={copy.body}
        actions={
          copy.action ? (
            <Button variant="danger-outline" size="md" stretch="auto" label={copy.action} onClick={openSecurityTab} />
          ) : undefined
        }
      />
    </div>
  );
});
