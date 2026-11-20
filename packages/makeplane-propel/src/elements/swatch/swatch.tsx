import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import type * as React from "react";

import { swatchVariants } from "./variants";

export type SwatchProps = Omit<useRender.ComponentProps<"span">, "className" | "style"> & {
  /** The disc's colour — any CSS `<color>` (a label's stored hex, an `rgb()` string). */
  fill: string;
};

/**
 * A filled 8px colour disc centred in the inherited `--node-size` box, so it sits exactly where an
 * icon would: the leading node of a label pill, or a `MenuItem`'s `icon` slot. Decorative
 * (`aria-hidden`) — the adjacent label carries the name. `fill` is the one styling input a consumer
 * supplies, because the colour is data rather than a token; the part applies it itself as
 * `--swatch-fill`, so no `style` prop is exposed.
 */
export function Swatch({ fill, render, ...props }: SwatchProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    "aria-hidden": true,
    className: swatchVariants(),
    style: { "--swatch-fill": fill } as React.CSSProperties,
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
