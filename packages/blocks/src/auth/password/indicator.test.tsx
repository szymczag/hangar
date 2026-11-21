/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Hangar: the indicator follows the fork's password policy (S9 in FORK.md): at least
// PASSWORD_MIN_LENGTH (15) code points, then a zxcvbn guessability estimate.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { E_PASSWORD_STRENGTH, PASSWORD_MIN_LENGTH } from "@plane/constants";
import { getStrengthInfo } from "./helper";
import { PasswordStrengthIndicator } from "./indicator";

const lengthCriterion = () => screen.getByText(`At least ${PASSWORD_MIN_LENGTH} characters`);

describe("PasswordStrengthIndicator", () => {
  it("uses the fork's 15-character minimum", () => {
    expect(PASSWORD_MIN_LENGTH).toBe(15);
  });

  it("shows a 14-character password as too short", () => {
    render(<PasswordStrengthIndicator password={"a".repeat(14)} />);

    expect(screen.getByText("Use at least 15 characters")).toBeTruthy();
    const meter = screen.getByRole("progressbar", { name: "Password strength" });
    expect(meter.getAttribute("aria-valuetext")).toBe("Use at least 15 characters");
    expect(lengthCriterion().className).not.toContain("text-success-primary");
  });

  it("counts code points, so 14 emoji are still too short", () => {
    render(<PasswordStrengthIndicator password={"🔑".repeat(14)} />);

    expect(screen.getByText("Use at least 15 characters")).toBeTruthy();
  });

  it("estimates a 15-character password instead of rejecting it for length", async () => {
    render(<PasswordStrengthIndicator password={"a".repeat(15)} />);

    expect(lengthCriterion().className).toContain("text-success-primary");
    // A repeated character passes the length rule but zxcvbn scores it as guessable.
    expect(await screen.findByText("Password is weak")).toBeTruthy();
    expect(screen.queryByText("Use at least 15 characters")).toBeNull();
  });

  it("accepts a precomputed strength result without estimating again", () => {
    render(
      <PasswordStrengthIndicator
        password="correct horse battery staple"
        isFocused
        strengthResult={{ score: 4, strength: E_PASSWORD_STRENGTH.STRENGTH_VALID, warning: null, suggestions: [] }}
      />
    );

    expect(screen.getByText("Password is very strong")).toBeTruthy();
  });
});

describe("getStrengthInfo", () => {
  it("reports a pending estimate rather than a verdict", () => {
    const info = getStrengthInfo({
      score: 0,
      strength: E_PASSWORD_STRENGTH.STRENGTH_NOT_VALID,
      warning: null,
      suggestions: [],
      isLoading: true,
    });
    expect(info.message).toBe("Checking password strength");
    expect(info.activeFragments).toBe(0);
  });
});
