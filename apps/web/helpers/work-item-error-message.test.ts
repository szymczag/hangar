/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { getWorkItemErrorMessage } from "./work-item-error-message";

const FALLBACK = "Error while updating work item";

describe("getWorkItemErrorMessage", () => {
  it("reads a field error, which is how a refused hierarchy move arrives", () => {
    expect(getWorkItemErrorMessage({ parent_id: ["Epic work items cannot have a parent"] }, FALLBACK)).toBe(
      "Epic work items cannot have a parent"
    );
  });

  it("reads the common error shapes", () => {
    expect(getWorkItemErrorMessage({ detail: "Not allowed" }, FALLBACK)).toBe("Not allowed");
    expect(getWorkItemErrorMessage({ error: "Nope" }, FALLBACK)).toBe("Nope");
    expect(getWorkItemErrorMessage({ non_field_errors: ["Bad state"] }, FALLBACK)).toBe("Bad state");
    expect(getWorkItemErrorMessage("Plain message", FALLBACK)).toBe("Plain message");
    expect(getWorkItemErrorMessage({ response: { data: { detail: "From axios" } } }, FALLBACK)).toBe("From axios");
  });

  it("prefers detail over an unrelated field", () => {
    expect(getWorkItemErrorMessage({ id: ["ignored"], detail: "The reason" }, FALLBACK)).toBe("The reason");
  });

  it("falls back when there is nothing to show", () => {
    expect(getWorkItemErrorMessage(undefined, FALLBACK)).toBe(FALLBACK);
    expect(getWorkItemErrorMessage({}, FALLBACK)).toBe(FALLBACK);
    expect(getWorkItemErrorMessage({ detail: "   " }, FALLBACK)).toBe(FALLBACK);
    expect(getWorkItemErrorMessage({ status: 400 }, FALLBACK)).toBe(FALLBACK);
  });

  it("bounds a long message", () => {
    expect(getWorkItemErrorMessage({ detail: "x".repeat(500) }, FALLBACK)).toHaveLength(200);
  });
});
