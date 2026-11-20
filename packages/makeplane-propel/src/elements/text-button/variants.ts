import { cva, cx, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

export const textButtonVariants = cva(
  cx(
    "inline-flex cursor-pointer items-center gap-1.5 rounded-xs transition-colors outline-none",
    // One line, like every other action in the library (`buttonGeometryVariants`): a text-only
    // action is still a control, and a wrapped label leaves a flanking icon centered against the
    // whole block instead of the line it labels.
    "whitespace-nowrap",
    "focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:ring-offset-1",
    "disabled:cursor-not-allowed disabled:text-disabled",
    "disabled:[&>[aria-hidden='true']]:text-icon-disabled",
  ),
  {
    variants: {
      variant: {
        primary: "text-link-primary hover:text-link-primary-hover",
        secondary: "text-tertiary hover:text-primary",
      },
      size: {
        md: "text-body-xs-medium [--node-size:var(--control-glyph-md)]",
        lg: "text-body-sm-medium [--node-size:var(--control-glyph-lg)]",
      },
    },
  },
);

type TextButtonVariantConfig = VariantProps<typeof textButtonVariants>;
export type TextButtonVariant = NonNullable<TextButtonVariantConfig["variant"]>;
export type TextButtonSize = NonNullable<TextButtonVariantConfig["size"]>;

export type TextButtonVariantProps = StrictVariantProps<typeof textButtonVariants>;

// The label stays unadorned; the root owns typography and state colors.
export const textButtonLabelVariants = cva("");
