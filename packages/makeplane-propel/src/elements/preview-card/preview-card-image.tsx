import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { previewCardImageVariants } from "./variants";

export type PreviewCardImageProps = Omit<useRender.ComponentProps<"img">, "className" | "style">;

/**
 * The thumbnail image shown inside the popup. Bakes in `w-full`, overflow-hidden, and object-cover
 * so the thumbnail always spans the card, clips, and fills its box — these are "always the same"
 * per the design spec. Height is set by the consumer's layout (native `height`, or the image's
 * intrinsic aspect ratio at full width).
 */
export function PreviewCardImage({ render, ...props }: PreviewCardImageProps) {
  const defaultProps: useRender.ElementProps<"img"> = { className: previewCardImageVariants() };
  return useRender({ defaultTagName: "img", render, props: mergeProps(defaultProps, props) });
}
