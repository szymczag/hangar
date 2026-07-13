import { useEffect, useMemo, useState } from "react";
import { E_PASSWORD_STRENGTH, PASSWORD_MIN_LENGTH } from "@plane/constants";
import type { PasswordStrengthResult } from "@plane/utils";
import { getPasswordLength, getPasswordStrengthResult } from "@plane/utils";

const emptyResult: PasswordStrengthResult = {
  score: 0,
  strength: E_PASSWORD_STRENGTH.EMPTY,
  warning: null,
  suggestions: [],
};

export type PasswordStrengthState = PasswordStrengthResult & {
  isLoading: boolean;
  error: string | null;
};

export const usePasswordStrength = (password: string): PasswordStrengthState => {
  const immediateResult = useMemo<PasswordStrengthResult>(() => {
    if (!password) return emptyResult;
    if (getPasswordLength(password) < PASSWORD_MIN_LENGTH) {
      return { ...emptyResult, strength: E_PASSWORD_STRENGTH.LENGTH_NOT_VALID };
    }
    return { ...emptyResult, strength: E_PASSWORD_STRENGTH.STRENGTH_NOT_VALID };
  }, [password]);
  const [resolved, setResolved] = useState<{ password: string; result: PasswordStrengthResult } | null>(null);
  const [failedPassword, setFailedPassword] = useState<string | null>(null);

  useEffect(() => {
    if (!password || getPasswordLength(password) < PASSWORD_MIN_LENGTH) return;

    let isCurrent = true;
    getPasswordStrengthResult(password)
      .then((result) => {
        if (!isCurrent) return undefined;
        setResolved({ password, result });
        setFailedPassword(null);
        return undefined;
      })
      .catch(() => {
        if (!isCurrent) return;
        setFailedPassword(password);
      });

    return () => {
      isCurrent = false;
    };
  }, [password]);

  const currentResult = resolved?.password === password ? resolved.result : immediateResult;
  const hasError = failedPassword === password;
  const needsEstimate = !!password && getPasswordLength(password) >= PASSWORD_MIN_LENGTH;

  return {
    ...currentResult,
    isLoading: needsEstimate && resolved?.password !== password && !hasError,
    error: hasError ? "Password strength could not be checked. Please try again." : null,
  };
};
