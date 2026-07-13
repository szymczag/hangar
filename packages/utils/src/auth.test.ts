import { describe, expect, it } from "vitest";
import { E_PASSWORD_STRENGTH } from "@plane/constants";
import { getPasswordLength, getPasswordStrengthResult } from "./auth";

describe("password strength policy", () => {
  it("rejects passwords shorter than 15 characters before estimating strength", async () => {
    const result = await getPasswordStrengthResult("Tr0ub4dor&3");

    expect(result.strength).toBe(E_PASSWORD_STRENGTH.LENGTH_NOT_VALID);
  });

  it("rejects long but obvious passwords", async () => {
    const result = await getPasswordStrengthResult("passwordpassword");

    expect(result.strength).toBe(E_PASSWORD_STRENGTH.STRENGTH_NOT_VALID);
  });

  it("accepts a long, memorable passphrase without composition rules", async () => {
    const result = await getPasswordStrengthResult("correct horse battery staple");

    expect(result.strength).toBe(E_PASSWORD_STRENGTH.STRENGTH_VALID);
  });

  it("returns estimator feedback for guessable passwords", async () => {
    const result = await getPasswordStrengthResult("passwordpassword");

    expect(result.warning || result.suggestions.length > 0).toBeTruthy();
  });

  it("counts Unicode code points consistently", () => {
    expect(getPasswordLength("😀".repeat(15))).toBe(15);
  });
});
