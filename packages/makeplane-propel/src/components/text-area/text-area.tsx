import { Field as BaseField } from "@base-ui/react/field";
import * as React from "react";

import {
  TextArea as TextAreaElement,
  type TextAreaSize,
  type TextAreaSurface,
} from "../../elements/text-area/text-area";

export type { TextAreaSize, TextAreaSurface };
export type { TextAreaResize } from "../../elements/text-area/text-area-group";

type BaseFieldControlProps = BaseField.Control.Props;
// `Field.Control` is input-shaped; restore the textarea-only native attrs (rows, cols, wrap…) minus
// the keys Field.Control already owns.
type NativeTextAreaProps = Omit<
  React.ComponentProps<"textarea">,
  keyof BaseFieldControlProps | "children" | "className" | "style"
>;

function assignRef<T>(ref: React.Ref<T> | undefined, node: T | null) {
  if (typeof ref === "function") return ref(node);
  else if (ref != null) (ref as React.RefObject<T | null>).current = node;
}

function lineHeightPx(computed: CSSStyleDeclaration): number {
  const parsed = parseFloat(computed.lineHeight);
  return Number.isFinite(parsed) ? parsed : parseFloat(computed.fontSize) * 1.2;
}

function borderYPx(computed: CSSStyleDeclaration): number {
  return parseFloat(computed.borderTopWidth) + parseFloat(computed.borderBottomWidth);
}

function paddingYPx(computed: CSSStyleDeclaration): number {
  return parseFloat(computed.paddingTop) + parseFloat(computed.paddingBottom);
}

// Last-resort default, used only when the `min-h-*` class on the element fails to resolve to a
// real computed value. Must match the `field` compound variants in `elements/text-area/variants.ts`
// (asserted by `internal/textarea-min-height.test.ts`).
const TEXT_AREA_DEFAULT_MIN_HEIGHT_REM: Record<TextAreaSize, number> = {
  md: 3.75,
  lg: 4.75,
  xl: 6.375,
  "2xl": 5.625,
};

function defaultMinHeightPx(element: HTMLTextAreaElement, size: TextAreaSize): number {
  const rootPx = parseFloat(getComputedStyle(element.ownerDocument.documentElement).fontSize);
  return TEXT_AREA_DEFAULT_MIN_HEIGHT_REM[size] * (Number.isFinite(rootPx) ? rootPx : 16);
}

/** Match content height, honoring the size `min-height` as the floor and `maxRows` as the cap. */
function syncTextAreaHeight(
  element: HTMLTextAreaElement,
  maxRows: number | undefined,
  size: TextAreaSize,
  surface: TextAreaSurface,
) {
  const previousOverflowY = element.style.overflowY;
  // Assumes `box-sizing: border-box` — Tailwind's own Preflight default, which every other class on
  // this leaf (padding, min-height) already assumes — so `height` is the whole visual box and
  // border always adds in.
  element.style.minHeight = "";
  const computed = getComputedStyle(element);
  const borderY = borderYPx(computed);
  // Prefer the computed `min-h-*` class so a stylesheet override is honored; fall back to the JS
  // default only if it fails to resolve (e.g. propel's CSS isn't loaded on this page).
  const computedMinHeight = parseFloat(computed.minHeight);
  const minHeight =
    surface === "field"
      ? computedMinHeight > 0
        ? computedMinHeight
        : defaultMinHeightPx(element, size)
      : 0;
  element.style.minHeight = minHeight > 0 ? `${minHeight}px` : "";

  element.style.overflowY = "hidden";
  element.style.height = "auto";

  let next = element.scrollHeight + borderY;
  if (minHeight > 0) {
    next = Math.max(next, minHeight);
  }

  if (maxRows != null) {
    const maxHeight = lineHeightPx(computed) * maxRows + paddingYPx(computed) + borderY;
    next = Math.min(next, Math.max(maxHeight, minHeight));
  }

  element.style.height = `${next}px`;
  element.style.overflowY = previousOverflowY;
}

function useTextAreaAutoResize(
  elementRef: React.RefObject<HTMLTextAreaElement | null>,
  enabled: boolean,
  maxRows: number | undefined,
  value: React.ComponentProps<"textarea">["value"],
  size: TextAreaSize,
  surface: TextAreaSurface,
) {
  const sync = React.useCallback(() => {
    const element = elementRef.current;
    if (element == null) return;
    if (!enabled) {
      element.style.height = "";
      element.style.minHeight = "";
      return;
    }
    syncTextAreaHeight(element, maxRows, size, surface);
  }, [elementRef, enabled, maxRows, size, surface]);

  React.useLayoutEffect(() => {
    sync();
  }, [sync, value]);

  React.useLayoutEffect(() => {
    const element = elementRef.current;
    if (element == null || !enabled) return;

    // Sync during observer delivery so the new height lands in the same frame. When that write
    // resizes the observed element, detach until the next frame: a same-depth change would
    // otherwise be reported as "ResizeObserver loop completed with undelivered notifications".
    // Form reset and other non-observer paths still schedule via rAF; they share a separate handle
    // from re-observe so a reset in the unobserve window cannot cancel the re-attach.
    let frame = 0;
    let reobserveFrame = 0;
    const scheduleSync = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(sync);
    };
    const observer = new ResizeObserver(() => {
      // Fractional: line height × maxRows can move the height by less than a pixel.
      const before = element.getBoundingClientRect().height;
      sync();
      if (element.getBoundingClientRect().height === before) return;
      observer.unobserve(element);
      cancelAnimationFrame(reobserveFrame);
      reobserveFrame = requestAnimationFrame(() => observer.observe(element));
    });
    observer.observe(element);

    const form = element.form;
    form?.addEventListener("reset", scheduleSync);

    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      cancelAnimationFrame(reobserveFrame);
      form?.removeEventListener("reset", scheduleSync);
    };
  }, [elementRef, enabled, sync]);

  return sync;
}

// `size` is omitted from `Field.Control`'s input-shaped props: its native `size` (width in
// characters) would collide with the styling axis below.
export type TextAreaProps = Omit<BaseFieldControlProps, "className" | "style" | "render" | "size"> &
  NativeTextAreaProps & {
    /** Text size for the textarea value. */
    size: TextAreaSize;
    /** Control presentation for standalone fields or embedded composer surfaces. */
    surface: TextAreaSurface;
    /**
     * Grow the control with its value, using the size min-height as the floor. Pair the `field`
     * surface with `TextAreaGroup` `resize="none"` so the native drag handle does not fight
     * content-driven height.
     *
     * @default false
     */
    autoResize?: boolean;
    /**
     * Maximum visible lines when `autoResize` is set. Further lines scroll inside the control.
     * Unbounded when omitted.
     */
    maxRows?: number;
    /** The default value of the textarea. Use when uncontrolled. */
    defaultValue?: React.ComponentProps<"textarea">["defaultValue"];
    /** The value of the textarea. Use when controlled. */
    value?: React.ComponentProps<"textarea">["value"];
  };

/**
 * Multi-line text field that automatically works inside `Field`. Base UI's `Field.Control` behavior
 * grafted onto the styled `elements` `TextArea` element (rule 1a) — behavior part outer, styled
 * part as the render target. Base UI ships no textarea control, so `Field.Control` renders the
 * styled `<textarea>` directly (this replaces the former `base/text-area` wrapper). Pair the
 * `field` surface with `TextAreaGroup`, which owns the native `resize` handle. `autoResize` grows
 * the control with its value; the ready-made `TextAreaField` turns the native handle off when it is
 * set.
 */
export function TextArea({
  size,
  surface,
  autoResize = false,
  maxRows,
  ref,
  onInput,
  ...props
}: TextAreaProps) {
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const syncHeight = useTextAreaAutoResize(
    textareaRef,
    autoResize,
    maxRows,
    props.value,
    size,
    surface,
  );
  const setRef = React.useCallback(
    (node: Element | null) => {
      textareaRef.current = node instanceof HTMLTextAreaElement ? node : null;
      const cleanup = assignRef(ref, node);
      if (typeof cleanup === "function") {
        return () => {
          textareaRef.current = null;
          cleanup();
        };
      }
    },
    [ref],
  );

  return (
    <BaseField.Control
      {...props}
      onInput={(event) => {
        // `onInput` rather than `onChange`: Field.Control already owns `onChange` for dirty/validity
        // tracking, and replacing it would drop that. The value is in the DOM by `input`.
        onInput?.(event);
        syncHeight();
      }}
      ref={setRef}
      render={<TextAreaElement size={size} surface={surface} autoResize={autoResize} />}
    />
  );
}
