import { Button } from "@components/button";
import { type ReactNode, useEffect, useRef } from "react";

type ConfirmDialogProps = {
	open: boolean;
	title: string;
	/** What is about to happen, in the user's terms. */
	description?: ReactNode;
	confirmLabel?: string;
	cancelLabel?: string;
	/** Disables both buttons and relabels confirm while the action is in flight. */
	pending?: boolean;
	pendingLabel?: string;
	/** Shown inside the dialog so a failed action doesn't dismiss it silently. */
	error?: string | null;
	onConfirm: () => void;
	onCancel: () => void;
};

/**
 * A modal confirmation built on the native `<dialog>` element.
 *
 * `showModal()` brings the focus trap, the inert page behind it, the top-layer
 * stacking and the Escape key for free — all of which a div-and-overlay
 * version has to reimplement, usually incompletely. The `cancel` event is
 * where Escape arrives, so it routes to the same handler as the Cancel button.
 */
export function ConfirmDialog({
	open,
	title,
	description,
	confirmLabel = "Delete",
	cancelLabel = "Cancel",
	pending = false,
	pendingLabel = "Deleting…",
	error,
	onConfirm,
	onCancel,
}: ConfirmDialogProps) {
	const dialogRef = useRef<HTMLDialogElement>(null);

	useEffect(() => {
		const dialog = dialogRef.current;
		if (dialog === null) {
			return;
		}

		if (open && !dialog.open) {
			dialog.showModal();
		} else if (!open && dialog.open) {
			dialog.close();
		}
	}, [open]);

	// Dismiss on a backdrop click. Bound natively rather than through `onClick`
	// because there is no keyboard counterpart to pair it with — Escape is the
	// keyboard route out, and it arrives as `cancel` below.
	useEffect(() => {
		const dialog = dialogRef.current;
		if (dialog === null) {
			return;
		}

		const handleClick = (event: MouseEvent) => {
			// The dialog is the target only when the click missed its contents,
			// which is to say it landed on the backdrop.
			if (event.target === dialog && !pending) {
				onCancel();
			}
		};

		dialog.addEventListener("click", handleClick);
		return () => dialog.removeEventListener("click", handleClick);
	}, [onCancel, pending]);

	return (
		<dialog
			aria-labelledby="confirm-dialog-title"
			className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-card border border-border bg-table p-6 text-ink shadow-card backdrop:bg-black/40"
			onCancel={(event) => {
				// Escape closes the dialog on its own; let the owner drive it
				// instead, so `open` and the element never disagree.
				event.preventDefault();
				if (!pending) {
					onCancel();
				}
			}}
			ref={dialogRef}
		>
			<h2 className="text-xl leading-heading" id="confirm-dialog-title">
				{title}
			</h2>

			{description && (
				<div className="mt-2 text-ink-subtle text-sm">{description}</div>
			)}

			{error && (
				<p
					className="mt-4 rounded-xl bg-negative-bg px-4 py-2 text-negative text-sm"
					role="alert"
				>
					{error}
				</p>
			)}

			<div className="mt-6 flex justify-end gap-3">
				<Button disabled={pending} onClick={onCancel} variant="secondary">
					{cancelLabel}
				</Button>
				<Button disabled={pending} onClick={onConfirm} variant="danger">
					{pending ? pendingLabel : confirmLabel}
				</Button>
			</div>
		</dialog>
	);
}
