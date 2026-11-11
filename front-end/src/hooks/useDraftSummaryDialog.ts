import { useCallback, useEffect, useRef, type RefObject, type SyntheticEvent } from "react";

function canRestore(element: HTMLElement | null): element is HTMLElement {
  if (!element?.isConnected || element === element.ownerDocument.body || !element.getClientRects().length) return false;
  if (element.matches(":disabled") || element.getAttribute("aria-disabled") === "true" || element.closest('[hidden], [inert], [aria-hidden="true"]')) return false;
  const style = element.ownerDocument.defaultView?.getComputedStyle(element);
  return style?.display !== "none" && style?.visibility !== "hidden" && style?.visibility !== "collapse";
}

/** Native dialog owns containment/isolation; only explicit dismissal restores this page's focus. */
export function useDraftSummaryDialog(open: boolean, scopeKey: string, fallbackRef: RefObject<HTMLElement | null>, onDismiss: () => void) {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const titleRef = useRef<HTMLHeadingElement | null>(null);
  const latest = useRef({ scopeKey, onDismiss });
  latest.current = { scopeKey, onDismiss };
  const active = useRef<{ dialog: HTMLDialogElement; previous: HTMLElement | null; scopeKey: string } | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!open || !dialog) return;
    const previous = dialog.ownerDocument.activeElement as HTMLElement | null;
    const run = { dialog, previous, scopeKey };
    active.current = run;
    if (!dialog.open) dialog.showModal();
    titleRef.current?.focus();
    return () => {
      if (active.current === run) active.current = null;
      if (dialog.open) dialog.close();
    };
  }, [open, scopeKey]);

  const dismiss = useCallback(() => {
    const run = active.current;
    if (!run || run.scopeKey !== latest.current.scopeKey) return;
    active.current = null;
    if (run.dialog.open) run.dialog.close();
    const target = canRestore(run.previous) ? run.previous : fallbackRef.current;
    if (canRestore(target)) target.focus();
    latest.current.onDismiss();
  }, [fallbackRef]);

  return { dialogRef, titleRef, dismiss,
    onCancel(event: SyntheticEvent<HTMLDialogElement>) { event.preventDefault(); dismiss(); },
    onClose() { if (!dialogRef.current?.open) dismiss(); },
  };
}
