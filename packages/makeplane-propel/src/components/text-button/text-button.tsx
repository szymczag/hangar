import { Button as BaseButton } from "@base-ui/react/button";
import type * as React from "react";

import {
  TextButton as TextButtonElement,
  TextButtonLabel,
  type TextButtonProps as TextButtonElementProps,
} from "../../elements/text-button";

export type { TextButtonSize, TextButtonVariant } from "../../elements/text-button";

export type TextButtonProps = Omit<
  TextButtonElementProps,
  "children" | "disabled" | "render" | "type"
> & {
  /** Icon rendered beside the label (inline-start by default), e.g. `<Icon icon={Plus} />`. */
  icon?: React.ReactNode;
  /**
   * Which side of the label the icon sits on.
   *
   * @default "start"
   */
  iconPosition?: "start" | "end";
  /** Visible action label. */
  label: string;
  /** Uses the native, non-focusable disabled state. */
  disabled?: boolean;
  /**
   * The button's form behavior.
   *
   * @default "button"
   */
  type?: "submit" | "reset" | "button";
};

/**
 * A native button for low-emphasis actions with lightweight text-only chrome. It lays out an
 * optional `icon` beside the label. Unlike AnchorButton, TextButton never changes to link semantics
 * and does not expose a render target.
 */
export function TextButton({
  variant,
  size,
  icon,
  iconPosition = "start",
  label,
  disabled,
  type = "button",
  ...props
}: TextButtonProps) {
  return (
    <BaseButton
      {...props}
      type={type}
      render={<TextButtonElement variant={variant} size={size} />}
      disabled={disabled}
    >
      {iconPosition === "start" ? icon : null}
      <TextButtonLabel>{label}</TextButtonLabel>
      {iconPosition === "end" ? icon : null}
    </BaseButton>
  );
}
