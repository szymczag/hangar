import { cva, type VariantProps } from "class-variance-authority";

import { linkChromeVariants } from "../../internal/link-chrome";
import { type StrictVariantProps } from "../../internal/variant-props";

// `AnchorButton` is a semantic anchor with inline-link chrome. Use `TextButton` for lightweight
// text-only actions; for a navigation link with button chrome, use `Button`'s render path.
export const anchorButtonVariants = linkChromeVariants;

type AnchorButtonVariantConfig = VariantProps<typeof anchorButtonVariants>;
export type AnchorButtonVariant = NonNullable<AnchorButtonVariantConfig["variant"]>;
export type AnchorButtonSize = NonNullable<AnchorButtonVariantConfig["size"]>;

export type AnchorButtonVariantProps = StrictVariantProps<typeof anchorButtonVariants>;

// The text label inside an AnchorButton. Carries the underline (Figma: underline spans the text
// only, not the flanking icons).
export const anchorButtonLabelVariants = cva("underline underline-offset-2");
