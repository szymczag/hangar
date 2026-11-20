import {
  LogoSpinner as LogoSpinnerElement,
  LogoSpinnerImage,
  type LogoSpinnerProps as LogoSpinnerElementProps,
  type LogoSpinnerSize,
} from "../../elements/logo-spinner";

export type { LogoSpinnerSize };

// The one place in propel that ships binary assets. The animated mark is a designed GIF (65
// frames), so it cannot be tokens and CSS like everything else here, and it comes as a pair: one
// artwork per theme. Beside each GIF sits a still of the fully drawn mark (frame 28 of that GIF,
// exported at the same size) for viewers who asked for reduced motion — a GIF cannot be paused
// from CSS, so the swap is the same trick as the theme swap: all four render, CSS paints one.
//
// These are plain asset imports, which every asset-aware bundler turns into a URL at BUILD time —
// Vite, webpack 5+, Parcel, or Rollup with an asset plugin. `.gif` and `.png` are external to
// propel's own build (`tsdown.config.ts`), so the imports survive into `dist` next to the files the
// `copy` option puts there, and the consumer's bundler resolves them.
//
// They must stay static imports: `new URL("./x.gif", import.meta.url)` looks equivalent and works
// in the browser build, but it is evaluated at RUNTIME against the module's own URL — so a server
// render (React Router's SPA prerender included) resolves it in Node and bakes the build machine's
// `file:///…/node_modules/…` path into the shipped HTML. A static import has no runtime component
// and is correct in both builds.
import DARK_STILL_SRC from "./logo-spinner-dark-still.png";
import DARK_SRC from "./logo-spinner-dark.gif";
import LIGHT_STILL_SRC from "./logo-spinner-light-still.png";
import LIGHT_SRC from "./logo-spinner-light.gif";

// Astro's assets plugin resolves an image import to an `ImageMetadata` object rather than a URL
// string, so unwrap it — every other bundler already hands us the string.
const url = (src: string | { src: string }) => (typeof src === "string" ? src : src.src);

export type LogoSpinnerProps = Omit<LogoSpinnerElementProps, "children"> & {
  /** Mark height: `sm` 24px, `md` 44px, `fluid` 24px stepping to 44px at the 640px breakpoint. */
  size: LogoSpinnerSize;
  /** Alternative text (required) — what the app is waiting on, e.g. "Loading Plane". */
  alt: string;
};

/**
 * The animated Plane mark, for the moments a whole screen is waiting — app boot, a splash screen, a
 * full-page route transition. For pending state inside a control or a section, use
 * `CircularProgress` (or a control's own loading state) instead: this is brand furniture, not a
 * status glyph.
 *
 * Both themes' artwork is rendered and CSS shows the one matching the active `data-theme`, so a
 * theme flip costs no JS and no second request. Under `prefers-reduced-motion: reduce` the same CSS
 * paints a still of the fully drawn mark instead of the animation. Only the visible image is in the
 * accessibility tree (the other three are `display: none`), so `alt` is announced once.
 */
export function LogoSpinner({ size, alt, ...props }: LogoSpinnerProps) {
  return (
    <LogoSpinnerElement {...props}>
      <LogoSpinnerImage src={url(LIGHT_SRC)} alt={alt} size={size} theme="light" />
      <LogoSpinnerImage src={url(DARK_SRC)} alt={alt} size={size} theme="dark" />
      <LogoSpinnerImage
        src={url(LIGHT_STILL_SRC)}
        alt={alt}
        size={size}
        theme="light"
        motion="still"
      />
      <LogoSpinnerImage
        src={url(DARK_STILL_SRC)}
        alt={alt}
        size={size}
        theme="dark"
        motion="still"
      />
    </LogoSpinnerElement>
  );
}
