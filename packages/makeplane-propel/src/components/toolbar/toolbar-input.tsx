import { Toolbar as BaseToolbar } from "@base-ui/react/toolbar";
import * as React from "react";

import {
  type ToolbarSize,
  ToolbarInput as ToolbarInputElement,
  type ToolbarInputProps as ToolbarInputElementProps,
} from "../../elements/toolbar";
import { ToolbarSizeContext } from "./toolbar-context";

export type ToolbarInputProps = Omit<
  BaseToolbar.Input.Props,
  // Native `<input size>` (character width) collides with the styling axis — same omit as
  // `elements/toolbar` and `Input` (rule 6b). Without it, `size?: number & ToolbarSize` collapses
  // to `undefined` only and `<ToolbarInput size="sm" />` is a TS2322.
  "className" | "style" | "render" | "aria-label" | "size"
> & {
  /** Size override; defaults to the surrounding `Toolbar`'s size. */
  size?: ToolbarSize;
  /** Accessible name for the field (placeholder is not a name). */
  "aria-label": string;
  /** Custom render for the underlying styled toolbar input. */
  render?: ToolbarInputElementProps["render"];
};

/**
 * An inline text input in the toolbar's roving tab order (e.g. a filter box) — Base UI's
 * `Toolbar.Input` grafted onto the styled miniature field, its height tracking the toolbar's size.
 * An `aria-label` is required.
 */
export function ToolbarInput({ size, render, ...props }: ToolbarInputProps) {
  const toolbarSize = React.useContext(ToolbarSizeContext);
  return (
    <BaseToolbar.Input
      {...props}
      render={<ToolbarInputElement size={size ?? toolbarSize} render={render} />}
    />
  );
}
