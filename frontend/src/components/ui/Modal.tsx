import React, { useEffect, useId, useRef } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  width?: string;
  closeLabel?: string;
  titleIcon?: React.ReactNode;
  contentClassName?: string;
}

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

let bodyScrollLockCount = 0;
let bodyOverflowBeforeLock = '';
const openDialogStack: symbol[] = [];

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (element) => {
      if (
        element.hidden ||
        element.closest('[hidden]') ||
        element.closest('[aria-hidden="true"]') ||
        element.getAttribute('type') === 'hidden'
      ) {
        return false;
      }

      let current: HTMLElement | null = element;
      while (current && current !== container) {
        const style = window.getComputedStyle(current);
        if (style.display === 'none' || style.visibility === 'hidden') {
          return false;
        }
        current = current.parentElement;
      }

      return true;
    }
  );
}

function lockBodyScroll() {
  if (bodyScrollLockCount === 0) {
    bodyOverflowBeforeLock = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
  }
  bodyScrollLockCount += 1;
}

function unlockBodyScroll() {
  bodyScrollLockCount = Math.max(0, bodyScrollLockCount - 1);
  if (bodyScrollLockCount === 0) {
    document.body.style.overflow = bodyOverflowBeforeLock;
  }
}

export const Modal: React.FC<ModalProps> = ({
  open,
  onClose,
  title,
  children,
  width = 'max-w-lg',
  closeLabel = 'Close dialog',
  titleIcon,
  contentClassName = 'overflow-y-auto px-4 py-4 sm:px-6 sm:py-5',
}) => {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const dialogIdRef = useRef(Symbol('dialog'));
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;

    const dialogId = dialogIdRef.current;
    previouslyFocusedRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    openDialogStack.push(dialogId);
    lockBodyScroll();

    const focusTimer = window.setTimeout(() => {
      const dialog = dialogRef.current;
      if (!dialog || dialog.contains(document.activeElement)) return;
      const [firstFocusable] = getFocusableElements(dialog);
      const focusTarget = firstFocusable ?? dialog;
      focusTarget.focus();
    }, 0);

    const handler = (e: KeyboardEvent) => {
      if (openDialogStack[openDialogStack.length - 1] !== dialogId) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        onCloseRef.current();
        return;
      }

      if (e.key !== 'Tab') return;

      const dialog = dialogRef.current;
      if (!dialog) return;
      const focusableElements = getFocusableElements(dialog);

      if (focusableElements.length === 0) {
        e.preventDefault();
        dialog.focus();
        return;
      }

      const firstFocusable = focusableElements[0];
      const lastFocusable = focusableElements[focusableElements.length - 1];
      const activeElement = document.activeElement;
      const focusIsOutsideDialog = !dialog.contains(activeElement);

      if (e.shiftKey && (activeElement === firstFocusable || focusIsOutsideDialog)) {
        e.preventDefault();
        lastFocusable.focus();
      } else if (!e.shiftKey && (activeElement === lastFocusable || focusIsOutsideDialog)) {
        e.preventDefault();
        firstFocusable.focus();
      }
    };

    document.addEventListener('keydown', handler);

    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('keydown', handler);

      const stackIndex = openDialogStack.lastIndexOf(dialogId);
      if (stackIndex >= 0) {
        openDialogStack.splice(stackIndex, 1);
      }
      unlockBodyScroll();

      const previouslyFocused = previouslyFocusedRef.current;
      if (previouslyFocused?.isConnected) {
        previouslyFocused.focus();
      }
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto p-2 sm:p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" aria-hidden="true" />
      <div className="relative z-10 flex min-h-full items-start justify-center sm:items-center">
        <div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          tabIndex={-1}
          className={`relative z-10 my-4 flex max-h-[calc(100vh-3rem)] max-h-[calc(100svh-3rem)] w-full flex-col overflow-hidden rounded-2xl border border-bg-border bg-bg-secondary shadow-2xl animate-fade-in sm:my-6 sm:max-h-[calc(100vh-5rem)] sm:max-h-[calc(100svh-5rem)] ${width}`}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex shrink-0 items-center justify-between border-b border-bg-border px-4 py-3 sm:px-6 sm:py-4">
            <div className="flex min-w-0 items-center gap-2.5">
              {titleIcon && <span aria-hidden="true">{titleIcon}</span>}
              <h2 id={titleId} className="truncate text-base font-semibold text-text-primary">
                {title}
              </h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={closeLabel}
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            >
              <X size={16} aria-hidden="true" />
            </button>
          </div>
          <div className={`min-h-0 ${contentClassName}`}>{children}</div>
        </div>
      </div>
    </div>
  );
};
