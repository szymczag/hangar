/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Hangar: useDialogDismissal is adapted to the 1.4 useOutsideClickDetector (no `enabled`
// argument), so the open/handler guard is checked here. @plane/hooks has no test runner.

import { useRef } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useDialogDismissal } from "@plane/hooks";

function Dialog({
  isOpen,
  handleClose,
  onOutsideClick,
  label,
}: {
  isOpen: boolean;
  handleClose?: () => void;
  onOutsideClick?: () => void;
  label: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  useDialogDismissal({ isOpen, handleClose, onOutsideClick, panelRef });
  return <div ref={panelRef}>{label}</div>;
}

describe("useDialogDismissal", () => {
  it("fires onOutsideClick for a press outside an open panel only", () => {
    const onOutsideClick = vi.fn();
    render(
      <>
        <Dialog isOpen onOutsideClick={onOutsideClick} label="panel" />
        <button type="button">outside</button>
      </>
    );

    fireEvent.mouseDown(screen.getByText("panel"));
    expect(onOutsideClick).not.toHaveBeenCalled();
    fireEvent.mouseDown(screen.getByText("outside"));
    expect(onOutsideClick).toHaveBeenCalledTimes(1);
  });

  it("ignores outside presses while closed", () => {
    const onOutsideClick = vi.fn();
    const { rerender } = render(<Dialog isOpen onOutsideClick={onOutsideClick} label="panel" />);
    rerender(<Dialog isOpen={false} onOutsideClick={onOutsideClick} label="panel" />);

    fireEvent.mouseDown(document.body);
    expect(onOutsideClick).not.toHaveBeenCalled();
  });

  it("closes only the topmost dialog on Escape", () => {
    const closeOuter = vi.fn();
    const closeInner = vi.fn();
    render(
      <>
        <Dialog isOpen handleClose={closeOuter} label="outer" />
        <Dialog isOpen handleClose={closeInner} label="inner" />
      </>
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(closeInner).toHaveBeenCalledTimes(1);
    expect(closeOuter).not.toHaveBeenCalled();
  });
});
