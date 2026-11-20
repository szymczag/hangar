import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { previewCardTitleVariants } from "./variants";

export type PreviewCardTitleProps = Omit<useRender.ComponentProps<"h2">, "className" | "style">;

/**
 * The card's primary heading — `text-body-sm-medium` per the design spec. Truncates to a single
 * line instead of wrapping (Figma titles are nowrap on the 296px card). Diverges from the shared
 * `internal/overlay-title` "md" step (`semibold`) — that step has no current consumer (this family
 * used to adopt it) and is lighter `medium` here per Figma, so it keeps its own recipe (rule 4a:
 * divergent styling stays per-family). When `children` is a string, bakes a native `title` so hover
 * recovers the full text past the truncation; pass `title` explicitly to override (or `title=""` to
 * suppress).
 */
export function PreviewCardTitle({ render, children, title, ...props }: PreviewCardTitleProps) {
  const defaultProps: useRender.ElementProps<"h2"> = {
    className: previewCardTitleVariants(),
    children,
    title: title !== undefined ? title : typeof children === "string" ? children : undefined,
  };
  return useRender({ defaultTagName: "h2", render, props: mergeProps(defaultProps, props) });
}
