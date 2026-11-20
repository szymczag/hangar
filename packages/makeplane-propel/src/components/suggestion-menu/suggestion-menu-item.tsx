import { mergeProps } from "@base-ui/react/merge-props";
import * as React from "react";

import {
  SuggestionMenuItem as SuggestionMenuItemElement,
  SuggestionMenuItemIcon,
  SuggestionMenuItemTitle,
  SuggestionMenuItemTrailing,
} from "../../elements/suggestion-menu";
import { useSuggestionMenuContext } from "./suggestion-menu-context";

export type SuggestionMenuItemProps = Omit<
  React.ComponentPropsWithoutRef<"div">,
  "className" | "style" | "children" | "role" | "aria-selected"
> & {
  /** Leading glyph, e.g. `<Heading1 />`. Sized to 16px and tinted `icon-secondary`. */
  icon?: React.ReactNode;
  /** Row label. A node, so the matched part of a query can be emphasized. */
  label: React.ReactNode;
  /**
   * Content pinned at the row's inline end, e.g. a plan badge. Non-interactive only: a press
   * anywhere in the menu keeps focus in the input, so a button or link here would never take
   * focus.
   */
  trailing?: React.ReactNode;
};

/**
 * A suggestion row. `onClick` runs when the row is chosen — by a click, or by `Enter`/`Tab`
 * forwarded through `SuggestionMenu`'s `actionsRef`. Pointer movement highlights the row, and a
 * press never takes focus from the input.
 */
export function SuggestionMenuItem({
  icon,
  label,
  trailing,
  id,
  ...props
}: SuggestionMenuItemProps) {
  const generatedId = React.useId();
  const rowId = id ?? generatedId;
  const { getSnapshot, subscribe, highlight } = useSuggestionMenuContext();
  const highlighted = React.useSyncExternalStore(
    subscribe,
    () => getSnapshot() === rowId,
    () => false,
  );

  const ownProps: React.ComponentPropsWithoutRef<"div"> = {
    id: rowId,
    role: "option",
    "aria-selected": highlighted,
    // `mousemove`, not `mouseenter`: a row scrolled under a resting pointer by the keyboard must
    // not steal the highlight back.
    onMouseMove: () => {
      if (!highlighted) highlight(rowId);
    },
  };

  return (
    <SuggestionMenuItemElement
      data-highlighted={highlighted ? "" : undefined}
      // Managed semantics last, so a consumer cannot override the listbox contract; event
      // handlers merge, so a consumer `onMouseMove` still runs alongside.
      {...mergeProps<"div">(props, ownProps)}
    >
      {icon != null ? <SuggestionMenuItemIcon>{icon}</SuggestionMenuItemIcon> : null}
      <SuggestionMenuItemTitle>{label}</SuggestionMenuItemTitle>
      {trailing != null ? (
        <SuggestionMenuItemTrailing>{trailing}</SuggestionMenuItemTrailing>
      ) : null}
    </SuggestionMenuItemElement>
  );
}
