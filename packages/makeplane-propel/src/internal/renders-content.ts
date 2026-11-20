import type * as React from "react";

/**
 * Whether a node renders anything. `null`, `undefined`, booleans and `""` render nothing, so a slot
 * wrapping one would still be laid out — an empty box that takes the row's gap. Ready-mades check
 * an optional node prop with this before wrapping it in its slot, so `trailing={count > 0 &&
 * count}` or `trailing=""` leaves no slot behind. `0` renders, so it counts as content.
 */
export function rendersContent(node: React.ReactNode): boolean {
  return node != null && typeof node !== "boolean" && node !== "";
}
