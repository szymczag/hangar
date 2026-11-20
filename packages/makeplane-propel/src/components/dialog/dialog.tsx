import { Dialog as BaseDialog } from "@base-ui/react/dialog";
import * as React from "react";

import { PayloadChildren } from "../../internal/payload-children";
import {
  AlertDialog,
  AlertDialogActions,
  AlertDialogBody,
  AlertDialogClose,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogIcon,
  AlertDialogIntro,
  AlertDialogTitle,
} from "../alert-dialog";
import { Button } from "../button";

export type DialogDiscard = {
  /**
   * Whether a close request must be confirmed right now — typically "the form has unsaved edits".
   * While `false`, the dialog closes as usual.
   */
  when: boolean;
  /**
   * Called after the person confirms, once the dialog has been asked to close. Reset draft state
   * here.
   */
  onDiscard?: () => void;
  /**
   * Alert title.
   *
   * @default "Discard changes?"
   */
  title?: React.ReactNode;
  /**
   * Alert description.
   *
   * @default "Your changes haven't been saved. Discarding them can't be undone."
   */
  description?: React.ReactNode;
  /**
   * Label of the destructive action that closes the dialog.
   *
   * @default "Discard"
   */
  discardLabel?: string;
  /**
   * Label of the action that dismisses the alert and returns to the dialog.
   *
   * @default "Keep editing"
   */
  keepLabel?: string;
};

/** The imperative actions exposed through `actionsRef`: `close()` and `unmount()`. */
export type DialogImperativeActions = BaseDialog.Root.Actions;

export type DialogProps = Omit<BaseDialog.Root.Props, "className" | "style"> & {
  /**
   * Ask before a dismissal while `when` is true: Escape, an outside press, and any `DialogClose`
   * raise an `AlertDialog` instead of closing. "Discard" then closes the dialog and calls
   * `onDiscard`; "Keep editing" returns to it. Closing from your own handler (Save, Post) is not a
   * dismissal and is never intercepted: set controlled `open` to `false`, or call
   * `actionsRef.current.close()`. Either of those while the alert is showing closes both.
   */
  discard?: DialogDiscard;
};

/**
 * The dialog Root — Base UI's context/state provider (renders no element of its own). Modal by
 * default; pass `disablePointerDismissal` to keep it open on outside clicks. A behavior-only role,
 * so it lives in `components` (rules 1a, 2); the styled parts live in `elements/dialog` and are
 * grafted onto Base UI behavior here.
 */
export function Dialog({
  discard,
  open,
  defaultOpen,
  onOpenChange,
  actionsRef,
  children,
  ...props
}: DialogProps) {
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen ?? false);
  const actions = React.useRef<DialogImperativeActions | null>(null);

  React.useImperativeHandle(
    actionsRef,
    () => ({
      close: () => actions.current?.close(),
      unmount: () => actions.current?.unmount(),
    }),
    [],
  );

  // The confirmation renders beside the trigger, so it outlives the popup. Whenever the dialog
  // closes by a path the guard does not intercept — controlled `open`, `actionsRef.close()`, the
  // discard itself — take the confirmation down with it, or it is left modal over a dialog that is
  // already gone. Mirrors the uncontrolled open state because only the controlled one is a prop.
  const dialogOpen = open ?? uncontrolledOpen;
  React.useEffect(() => {
    if (!dialogOpen) setConfirmOpen(false);
  }, [dialogOpen]);

  const guard = discard ? (
    <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
      <AlertDialogContent>
        <AlertDialogBody>
          <AlertDialogHeader>
            <AlertDialogIcon variant="danger" />
            <AlertDialogIntro>
              <AlertDialogTitle>{discard.title ?? "Discard changes?"}</AlertDialogTitle>
              <AlertDialogDescription>
                {discard.description ??
                  "Your changes haven't been saved. Discarding them can't be undone."}
              </AlertDialogDescription>
            </AlertDialogIntro>
          </AlertDialogHeader>
        </AlertDialogBody>
        <AlertDialogActions>
          <Button
            stretch="auto"
            variant="secondary"
            size="md"
            render={<AlertDialogClose />}
            label={discard.keepLabel ?? "Keep editing"}
          />
          <Button
            stretch="auto"
            variant="danger"
            size="md"
            label={discard.discardLabel ?? "Discard"}
            onClick={() => {
              setConfirmOpen(false);
              // An imperative close is not a dismissal, so the guard below lets it through.
              actions.current?.close();
              discard.onDiscard?.();
            }}
          />
        </AlertDialogActions>
      </AlertDialogContent>
    </AlertDialog>
  ) : null;

  return (
    <BaseDialog.Root
      {...props}
      open={open}
      defaultOpen={defaultOpen}
      actionsRef={actions}
      onOpenChange={(nextOpen, details) => {
        if (!nextOpen && discard?.when && details.reason !== "imperative-action") {
          details.cancel();
          setConfirmOpen(true);
          return;
        }
        setUncontrolledOpen(nextOpen);
        onOpenChange?.(nextOpen, details);
      }}
    >
      {typeof children === "function" ? (
        ({ payload }) => (
          <>
            <PayloadChildren render={children} payload={payload} />
            {guard}
          </>
        )
      ) : (
        <>
          {children}
          {guard}
        </>
      )}
    </BaseDialog.Root>
  );
}
