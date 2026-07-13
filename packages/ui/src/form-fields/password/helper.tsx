/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { E_PASSWORD_STRENGTH } from "@plane/constants";
import type { PasswordStrengthResult } from "@plane/utils";

export interface StrengthInfo {
  message: string;
  textColor: string;
  activeFragments: number;
}

/**
 * Get strength information including message, color, and active fragments
 */
export const getStrengthInfo = ({
  score,
  strength,
  isLoading,
}: PasswordStrengthResult & { isLoading?: boolean }): StrengthInfo => {
  if (isLoading) {
    return {
      message: "Checking password strength",
      textColor: "text-primary",
      activeFragments: 0,
    };
  }

  switch (strength) {
    case E_PASSWORD_STRENGTH.EMPTY:
      return {
        message: "Please enter your password",
        textColor: "text-primary",
        activeFragments: 0,
      };
    case E_PASSWORD_STRENGTH.LENGTH_NOT_VALID:
      return {
        message: "Use at least 15 characters",
        textColor: "text-danger-primary",
        activeFragments: 1,
      };
    case E_PASSWORD_STRENGTH.STRENGTH_NOT_VALID:
      return {
        message: score <= 1 ? "Password is weak" : "Password is fair; make it harder to guess",
        textColor: "text-orange-500",
        activeFragments: Math.max(1, score),
      };
    case E_PASSWORD_STRENGTH.STRENGTH_VALID:
      return {
        message: score === 4 ? "Password is very strong" : "Password is strong",
        textColor: "text-success-primary",
        activeFragments: score,
      };
    default:
      return {
        message: "Please enter your password",
        textColor: "text-primary",
        activeFragments: 0,
      };
  }
};

/**
 * Get fragment color based on position and active state
 */
export const getFragmentColor = (fragmentIndex: number, activeFragments: number): string => {
  if (fragmentIndex >= activeFragments) {
    return "bg-layer-1";
  }

  switch (activeFragments) {
    case 1:
      return "bg-danger-primary";
    case 2:
      return "bg-orange-500";
    case 3:
    case 4:
      return "bg-success-primary";
    default:
      return "bg-layer-1";
  }
};
