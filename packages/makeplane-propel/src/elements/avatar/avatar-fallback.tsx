import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type AvatarFallbackVariantProps, avatarFallbackVariants } from "./variants";

export type { AvatarFallbackVariant } from "./variants";

/** Props for {@link AvatarFallback}, plus a `variant`. */
export type AvatarFallbackProps = Omit<useRender.ComponentProps<"span">, "className" | "style"> &
  AvatarFallbackVariantProps;

/**
 * The styled avatar fallback (colored initials, or the neutral anonymous-icon surface).
 * Base-UI-agnostic — graft the Base UI `Avatar.Fallback` (shown while the image is
 * absent/loading/failed) in `components` via `<BaseAvatar.Fallback render={<AvatarFallback/>} />`.
 */
export function AvatarFallback({ variant, render, ...props }: AvatarFallbackProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: avatarFallbackVariants({ variant }),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
