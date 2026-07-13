/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { CircleCheck } from "lucide-react";
import React from "react";
import { E_PASSWORD_STRENGTH } from "@plane/constants";
import { cn, getPasswordCriteria, type PasswordStrengthResult } from "@plane/utils";
import { getStrengthInfo, getFragmentColor } from "./helper";
import { usePasswordStrength } from "./use-password-strength";

export interface PasswordStrengthIndicatorProps {
  password: string;
  showCriteria?: boolean;
  isFocused?: boolean;
  strengthResult?: PasswordStrengthResult;
}

type PasswordStrengthIndicatorContentProps = Omit<PasswordStrengthIndicatorProps, "strengthResult"> & {
  strengthResult: PasswordStrengthResult;
};

function PasswordStrengthIndicatorContent({
  password,
  showCriteria = true,
  isFocused = false,
  strengthResult,
}: PasswordStrengthIndicatorContentProps) {
  const criteria = getPasswordCriteria(password, strengthResult.strength);
  const strengthInfo = getStrengthInfo(strengthResult);
  const feedback = strengthResult.warning || strengthResult.suggestions[0];

  const isPasswordMeterVisible = isFocused || strengthResult.strength !== E_PASSWORD_STRENGTH.STRENGTH_VALID;

  if ((!password && !showCriteria) || !isPasswordMeterVisible) {
    return null;
  }

  return (
    <div className={cn("space-y-3")}>
      {/* Strength Indicator */}
      <div className="space-y-2">
        <div
          className="flex w-full gap-1 transition-all duration-300 ease-linear"
          role="progressbar"
          aria-label="Password strength"
          aria-valuemin={0}
          aria-valuemax={4}
          aria-valuenow={strengthResult.score}
          aria-valuetext={strengthInfo.message}
        >
          {[0, 1, 2, 3].map((fragmentIndex) => (
            <div
              key={fragmentIndex}
              className={cn(
                "h-1 flex-1 rounded-xs transition-all duration-300 ease-in-out",
                getFragmentColor(fragmentIndex, strengthInfo.activeFragments)
              )}
            />
          ))}
        </div>

        {/* Strength Message */}
        {password && (
          <div aria-live="polite">
            <p className={cn("!text-13 font-medium", strengthInfo.textColor)}>{strengthInfo.message}</p>
            {feedback && <p className="mt-1 text-11 text-secondary">{feedback}</p>}
          </div>
        )}
      </div>

      {/* Criteria list */}
      {showCriteria && (
        <div className="flex flex-wrap gap-2">
          {criteria.map((criterion) => (
            <div key={criterion.key} className="flex items-center gap-1.5">
              <div className="flex items-center justify-center p-0.5">
                <CircleCheck
                  className={cn("h-3 w-3 flex-shrink-0", {
                    "text-success-primary": criterion.isValid,
                    "text-primary": !criterion.isValid,
                  })}
                />
              </div>
              <span
                className={cn("!text-11", {
                  "text-success-primary": criterion.isValid,
                  "text-primary": !criterion.isValid,
                })}
              >
                {criterion.label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EstimatedPasswordStrengthIndicator(props: Omit<PasswordStrengthIndicatorProps, "strengthResult">) {
  const strengthResult = usePasswordStrength(props.password);

  return <PasswordStrengthIndicatorContent {...props} strengthResult={strengthResult} />;
}

export function PasswordStrengthIndicator({ strengthResult, ...props }: PasswordStrengthIndicatorProps) {
  if (strengthResult) {
    return <PasswordStrengthIndicatorContent {...props} strengthResult={strengthResult} />;
  }

  return <EstimatedPasswordStrengthIndicator {...props} />;
}
