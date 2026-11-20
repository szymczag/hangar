import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  type ListSectionPanelContentVariantProps,
  listSectionPanelContentVariants,
} from "./variants";

export type ListSectionPanelContentProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style"
> &
  ListSectionPanelContentVariantProps;

/**
 * Wraps a `ListSection`'s rows in the Collapsible panel, restoring the heading-to-first-row gap
 * without the horizontal inset/prose `CollapsiblePanelContent` carries (rows own their own
 * padding).
 */
export function ListSectionPanelContent({ render, ...props }: ListSectionPanelContentProps) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps({ className: listSectionPanelContentVariants() }, props),
  });
}
