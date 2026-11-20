import * as React from "react";

import {
  SuggestionMenuGroup as SuggestionMenuGroupElement,
  SuggestionMenuLabel,
} from "../../elements/suggestion-menu";

export type SuggestionMenuGroupProps = Omit<
  React.ComponentPropsWithoutRef<"div">,
  "className" | "style" | "role" | "aria-labelledby"
> & {
  /** Section heading shown above the rows. Also names the group for assistive tech. */
  label?: React.ReactNode;
};

/**
 * A section of `SuggestionMenuItem` rows, with an optional heading. Sections are divided by a
 * hairline; the last draws none.
 */
export function SuggestionMenuGroup({ label, children, ...props }: SuggestionMenuGroupProps) {
  const labelId = React.useId();
  const hasLabel = label != null;
  return (
    <SuggestionMenuGroupElement
      {...props}
      role="group"
      aria-labelledby={hasLabel ? labelId : undefined}
    >
      {hasLabel ? <SuggestionMenuLabel id={labelId}>{label}</SuggestionMenuLabel> : null}
      {children}
    </SuggestionMenuGroupElement>
  );
}
