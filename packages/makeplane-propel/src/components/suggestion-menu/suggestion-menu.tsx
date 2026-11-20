import { mergeProps } from "@base-ui/react/merge-props";
import * as React from "react";

import {
  SuggestionMenu as SuggestionMenuElement,
  type SuggestionMenuProps as SuggestionMenuElementProps,
} from "../../elements/suggestion-menu";
import { useHeldWidth } from "../../internal/popup-width";
import { createSuggestionMenuStore, SuggestionMenuContext } from "./suggestion-menu-context";

/** Imperative handle for the input that keeps focus while the menu is open. */
export type SuggestionMenuActions = {
  /**
   * Handles a key press forwarded from the input. `ArrowDown`/`ArrowUp` move the highlight by one
   * row, `PageDown`/`PageUp` by a page (10 rows), and `Home`/`End` jump to the first/last row;
   * `Enter` and `Tab` choose the highlighted row. Returns `true` when the menu used the key — the
   * caller should then call `preventDefault()` so the input does not act on it too. A menu key
   * counts as used even when the highlight does not move (`loopFocus={false}` at the ends of the
   * list), so the host never acts on a key the menu claimed.
   */
  handleKeyDown: (event: Pick<KeyboardEvent, "key">) => boolean;
};

export type SuggestionMenuProps = Omit<
  React.ComponentPropsWithoutRef<"div">,
  "className" | "style" | "role"
> & {
  /**
   * Receives the menu's `SuggestionMenuActions`. Forward the input's key presses to
   * `actionsRef.current.handleKeyDown` — the menu never takes focus, so it never sees them itself.
   */
  actionsRef?: React.Ref<SuggestionMenuActions>;
  /**
   * Whether the highlight wraps from the last row to the first (and back) at the ends of the list.
   *
   * @default true
   */
  loopFocus?: boolean;
  /**
   * Runs whenever the highlighted row changes, with its `id` (or `null` when the menu has no rows).
   * Point the input's `aria-activedescendant` at it, so assistive tech announces the highlight
   * while focus stays in the input.
   */
  onHighlightChange?: (id: string | null) => void;
  /**
   * `fixed` is the 320px design column. `fit` sizes the menu to its widest row, between 204px and
   * 400px like `Menu`, so short lists leave no empty space. While mounted, a `fit` menu only grows:
   * filtering out wide rows never narrows it, so the width does not jump as someone types. `fit` is
   * bounded by the viewport, not its container: in a container narrower than 204px it overflows, so
   * use `fixed` there.
   *
   * @default "fixed"
   */
  width?: SuggestionMenuElementProps["width"];
};

const OPTION_SELECTOR = '[role="option"]';

/** Rows moved by `PageDown`/`PageUp` — a fixed page, so hosts need no measuring. */
const PAGE_SIZE = 10;

/**
 * A list of suggestions that follows an input which keeps focus — a `/` command menu in an editor,
 * `@` mentions, query completions. Unlike `Menu` it never moves focus: the input forwards its key
 * presses through `actionsRef`, and the menu owns which row is highlighted. The highlight starts on
 * the first row and falls back to it whenever the highlighted row is filtered out.
 *
 * Renders the `listbox`; compose `SuggestionMenuGroup` sections of `SuggestionMenuItem` rows inside
 * it. Positioning is the host's job — the menu renders in place.
 *
 * Wire the input as a combobox: give the menu an `id`, point the input's `aria-controls` at it, and
 * mirror `onHighlightChange` into the input's `aria-activedescendant`, so the highlight is
 * announced while focus stays in the input. Memoize the row list: otherwise the host re-render from
 * that mirror re-renders every `SuggestionMenuItem` on each arrow key.
 */
export function SuggestionMenu({
  actionsRef,
  loopFocus = true,
  onHighlightChange,
  width,
  ...props
}: SuggestionMenuProps) {
  const listRef = React.useRef<HTMLDivElement>(null);
  const [context] = React.useState(createSuggestionMenuStore);
  const { getSnapshot, subscribe, highlight } = context;
  const highlightedId = React.useSyncExternalStore(subscribe, getSnapshot, () => null);
  const [, bump] = React.useReducer((n: number) => n + 1, 0);
  // `fit` holds the widest width reached while mounted, so filtering never narrows the menu.
  const holdRef = useHeldWidth(width === "fit");
  const setList = React.useCallback(
    (node: HTMLDivElement | null) => {
      listRef.current = node;
      holdRef?.(node);
    },
    [holdRef],
  );

  // Rows in DOM order, so sections and filtering never need an index of their own.
  const getOptions = React.useCallback(
    () => Array.from(listRef.current?.querySelectorAll<HTMLElement>(OPTION_SELECTOR) ?? []),
    [],
  );

  // Rows come and go as the query changes. After every render, keep the highlight on a row that is
  // still there, falling back to the first. No deps on purpose: the rows are children, and any
  // render can change them. `highlight` is a no-op when the id is unchanged, so it settles in one
  // pass.
  React.useLayoutEffect(() => {
    const options = getOptions();
    if (options.some((option) => option.id === getSnapshot())) return;
    highlight(options[0]?.id ?? null);
    // Rows subscribe in passive effects, so a store-only write on mount could paint with no
    // highlighted row. A synchronous re-render flushes those effects first, and the rows' store
    // subscriptions then pick up the new highlight before paint.
    if (getSnapshot() !== highlightedId) bump();
  });
  // The host points its input's `aria-activedescendant` at the highlighted row.
  React.useEffect(() => {
    onHighlightChange?.(highlightedId);
  }, [highlightedId, onHighlightChange]);

  const moveHighlight = React.useCallback(
    (current: number, delta: number, length: number) => {
      let next = current === -1 ? (delta >= 0 ? 0 : length - 1) : current + delta;
      if (next < 0 || next >= length) {
        if (!loopFocus) return current === -1 ? 0 : current;
        next = (next + length) % length;
      }
      return next;
    },
    [loopFocus],
  );

  React.useImperativeHandle(
    actionsRef,
    () => ({
      handleKeyDown(event) {
        // Typing belongs to the host input; reject it before walking the option collection.
        let delta = 0;
        if (event.key === "ArrowDown") delta = 1;
        else if (event.key === "ArrowUp") delta = -1;
        else if (event.key === "PageDown") delta = PAGE_SIZE;
        else if (event.key === "PageUp") delta = -PAGE_SIZE;
        else if (
          event.key !== "Home" &&
          event.key !== "End" &&
          event.key !== "Enter" &&
          event.key !== "Tab"
        )
          return false;

        const options = getOptions();
        if (options.length === 0) return false;
        const current = options.findIndex((option) => option.id === getSnapshot());

        if (event.key === "Enter" || event.key === "Tab") {
          options[Math.max(current, 0)]?.click();
          return true;
        }

        if (event.key === "Home" || event.key === "End") {
          const target = options[event.key === "Home" ? 0 : options.length - 1];
          if (target && target.id !== getSnapshot()) {
            highlight(target.id);
            target.scrollIntoView({ block: "nearest" });
          }
          return true;
        }

        const next = moveHighlight(current, delta, options.length);
        // `loopFocus={false}` at the ends: the key is still claimed (return `true` below) so the
        // host never acts on it, even though the highlight stays put.
        if (next !== current) {
          const target = options[next];
          if (target) {
            highlight(target.id);
            target.scrollIntoView({ block: "nearest" });
          }
        }
        return true;
      },
    }),
    [getOptions, moveHighlight, getSnapshot, highlight],
  );

  return (
    <SuggestionMenuContext.Provider value={context}>
      {/* The intrinsic `render` target carries the ref, so it works on React 18 as well as 19. */}
      <SuggestionMenuElement
        role="listbox"
        width={width}
        render={<div ref={setList} />}
        {...mergeProps<"div">(
          // A press on a row or a heading keeps focus (and the caret) in the input it is
          // completing. A press that targets the list itself is the scrollbar — preventing the
          // default there would make the thumb undraggable — and it takes no focus anyway.
          {
            onMouseDown: (event) => {
              if (event.target !== event.currentTarget) event.preventDefault();
            },
          },
          props,
        )}
      />
    </SuggestionMenuContext.Provider>
  );
}
