# Hangar brand assets

`/hangar-logo.png` is the canonical Hangar logo artwork. Its letterforms, white
wordmark, dark outline, blue gradients, proportions, and glow are part of the
brand and must not be re-typeset or recolored for a theme.

The other files in this directory, along with the app favicons, PWA icons,
Open Graph images, email logo, and loading mark, are generated from that source:

```sh
pnpm generate:brand-assets
```

Run `pnpm check:brand-assets` to verify that checked-in derivatives match the
canonical source. Layout-specific code may resize the artwork or provide a
contrasting background, but it must not replace the original colors or
letterforms.
