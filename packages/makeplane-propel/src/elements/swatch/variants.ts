import { cva } from "class-variance-authority";

// A filled 8px disc — a label's or state's colour — centred in the `--node-size` box its host
// declares, so it takes the slot an `Icon` would and lines up with one across rows (a pill's
// leading node, a menu row's `icon`). The disc is a pseudo-element so the box, not the disc, is
// the flex item. The fill arrives as `--swatch-fill`, set inline by the part from its `fill` prop:
// the colour is user data (a stored hex), not a token, so no utility can name it.
export const swatchVariants = cva(
  "inline-flex size-(--node-size) shrink-0 items-center justify-center after:size-2 after:rounded-full after:bg-(--swatch-fill) after:content-['']",
);
