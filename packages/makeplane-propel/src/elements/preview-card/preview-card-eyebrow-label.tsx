import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { previewCardEyebrowLabelVariants } from "./variants";

export type PreviewCardEyebrowLabelProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/**
 * The single-line identifier text inside a `PreviewCardEyebrow` (an issue key, …). Muted one step
 * further than the description and truncates instead of wrapping. Not the card's heading — cycle /
 * module / release / intake names belong in `PreviewCardTitle` (optionally inside the eyebrow,
 * beside the icon). When `children` is a string, bakes a native `title` so hover recovers the full
 * text past the truncation; pass `title` explicitly to override (or `title=""` to suppress).
 */
export function PreviewCardEyebrowLabel({
  render,
  children,
  title,
  ...props
}: PreviewCardEyebrowLabelProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: previewCardEyebrowLabelVariants(),
    children,
    title: title !== undefined ? title : typeof children === "string" ? children : undefined,
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
