import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { previewCardEyebrowVariants } from "./variants";

export type PreviewCardEyebrowProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * Lays an optional leading node beside text on one row. The slot is unstyled flex — pass an icon, a
 * 16×16 filled type indicator (Figma's issue frame), or any other leading glyph. Stories use the
 * shared `internal/Icon` at `tint="secondary" size="md"` as a stand-in. Issue cards put a
 * `PreviewCardEyebrowLabel` identifier (an issue key) here ABOVE a separate `PreviewCardTitle`.
 * Cycle / module / release / intake cards put `PreviewCardTitle` in this row and skip
 * `PreviewCardEyebrowLabel` — those canvases have no muted identifier. Compose it only when the
 * card has a leading glyph; a card without one renders `PreviewCardTitle` directly inside
 * `PreviewCardBody`.
 */
export function PreviewCardEyebrow({ render, ...props }: PreviewCardEyebrowProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: previewCardEyebrowVariants(),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
