"use client";

import { useEffect, useRef, type DialogHTMLAttributes, type ReactNode } from "react";

interface ModalDialogProps extends Omit<DialogHTMLAttributes<HTMLDialogElement>, "open" | "onClose"> {
  open: boolean;
  /** Called for every close, including Escape. */
  onClose: () => void;
  children: ReactNode;
}

/** Native <dialog> opened with showModal(), so focus trapping and Escape come from the browser. */
export function ModalDialog({ open, onClose, children, ...rest }: ModalDialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog ref={ref} onClose={onClose} {...rest}>
      {children}
    </dialog>
  );
}
