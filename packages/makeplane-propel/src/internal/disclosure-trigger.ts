import { cx } from "class-variance-authority";

/**
 * The disclosure trigger core shared by accordion and collapsible (rule 4a): a `group`-carrying row
 * (its `DisclosureIndicator` reads the open state) with the shared type treatment, focus ring, and
 * disabled dimming. Families add their own geometry and `--node-size` on the family trigger — never
 * here — so there is never a second `--node-size` utility competing on the same element
 * (same-specificity same-property classes cascade by stylesheet order, not by position in the class
 * list). Today that split is:
 *
 * - Accordion: `p-3` + `hover:bg-layer-transparent-hover` + `--node-size:0.875rem`; title uses
 *   `disclosureTriggerTitleClass` (`flex-1`) so the caret sits trail-end.
 * - Collapsible: `min-w-0 flex-1` + `px-3 py-2` (no hover fill — Figma has no hover axis) +
 *   `--node-size:1rem`; title is a family cva without `flex-1` so Figma packs
 *   `[icon?][title][chevron]` as a left cluster. The trigger lives in `CollapsibleHeader`; leftover
 *   space stays the toggle hit target so a trailing action can sit at the inline-end.
 *
 * `disclosureTriggerTitleClass` is the growing, wrapping label used where the caret is trail-end
 * (Accordion today). Collapsible does not import it.
 */
export const disclosureTriggerClass = cx(
  "group flex items-center gap-2 text-start",
  "text-body-sm-medium text-primary",
  "cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-accent-strong",
  // Dim + block the cursor for BOTH disabled spellings: the native `disabled` attribute (used when a
  // trigger is disabled directly) and Base UI's `data-disabled`/`aria-disabled` (set when the
  // enclosing accordion/collapsible item is disabled — those keep the trigger focusable, so no
  // native `disabled` attribute lands and `:disabled` alone would never match).
  "disabled:cursor-not-allowed disabled:opacity-60",
  "data-disabled:cursor-not-allowed data-disabled:opacity-60",
);
export const disclosureTriggerTitleClass = "min-w-0 flex-1 text-start";
