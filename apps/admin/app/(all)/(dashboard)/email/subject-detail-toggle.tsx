/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { ToggleSwitch } from "@plane/ui";
// hooks
import { useInstance } from "@/hooks/store";

/**
 * The one header OpenPGP cannot cover.
 *
 * Everything else in an encrypted notification -- the real subject, the body,
 * comments, attachments -- is inside the encrypted MIME entity. The outer
 * Subject is not, so it reaches the mail provider, its logs and its backups in
 * the clear. Saying what changed there makes an inbox triageable and tells the
 * provider what people are working on. That is a trade, so it is an explicit
 * choice rather than a default.
 */
export const SubjectDetailToggle = observer(function SubjectDetailToggle() {
  const { formattedConfig, updateInstanceConfigurations } = useInstance();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isEnabled = formattedConfig?.OPENPGP_SUBJECT_DETAIL === "1";

  const handleToggle = async () => {
    const next = isEnabled ? "0" : "1";
    setIsSubmitting(true);
    try {
      await updateInstanceConfigurations({ OPENPGP_SUBJECT_DETAIL: next });
      setToast({
        title: next === "1" ? "Subjects now describe the work item" : "Subjects are generic again",
        message:
          next === "1"
            ? "Encrypted notifications name the work item, its title and the commenter in the Subject header."
            : "Encrypted notifications use a generic Subject that reveals nothing.",
        type: TOAST_TYPE.SUCCESS,
      });
    } catch (_error) {
      setToast({
        title: "Could not change the Subject setting",
        message: "The instance configuration was not updated. Please try again.",
        type: TOAST_TYPE.ERROR,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!formattedConfig) return null;

  return (
    <section className="mt-6 max-w-4xl rounded-md border border-subtle bg-layer-2 p-5">
      <div className="flex items-start justify-between gap-6">
        <div>
          <div className="text-13 font-medium text-primary">Describe encrypted notifications in the Subject</div>
          <p className="mt-1 text-12 leading-5 text-secondary">
            Off, every encrypted notification is sent as &ldquo;Encrypted Hangar notification&rdquo;. On, the Subject
            names the work item, its title and who commented &mdash; for example{" "}
            <span className="font-mono text-primary">INFRA-3 updates: Broken login flow - new comment from Ada L</span>.
          </p>
          <p className="mt-2 text-12 leading-5 text-tertiary">
            The Subject is the only part of an encrypted message that is not encrypted. It is visible to the mail
            provider, in its logs and backups, and to anyone who can see the mailbox list. The body, comments and
            attachments stay protected either way.
          </p>
        </div>
        <ToggleSwitch value={isEnabled} onChange={handleToggle} size="sm" disabled={isSubmitting} />
      </div>
    </section>
  );
});
