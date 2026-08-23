import { type ReactNode, useEffect, useRef } from "react";

type ModalProps = {
	children: ReactNode;
	onClose: () => void;
	open: boolean;
	title: string;
};

export function Modal({ children, onClose, open, title }: ModalProps) {
	const ref = useRef<HTMLDialogElement>(null);

	useEffect(() => {
		const dialog = ref.current;
		if (dialog === null) {
			return;
		}

		if (open && !dialog.open) {
			dialog.showModal();
		} else if (!open && dialog.open) {
			dialog.close();
		}
	}, [open]);

	return (
		// biome-ignore lint/a11y/useKeyWithClickEvents: <dialog> already closes on Escape natively; this onClick only adds backdrop-click dismissal for mouse users.
		<dialog
			className="fixed inset-0 m-0 h-full max-h-none w-full max-w-none bg-transparent p-4 backdrop:bg-black/60"
			onClick={(event) => {
				if (event.target === ref.current) {
					onClose();
				}
			}}
			onClose={onClose}
			ref={ref}
		>
			<div className="mx-auto flex h-full max-w-md items-center">
				<div className="w-full rounded-card border border-border bg-surface p-6 text-ink">
					<div className="flex items-center justify-between">
						<h2 className="text-xl leading-heading tracking-decreased">
							{title}
						</h2>
						<button
							aria-label="Close"
							className="text-ink-subtle hover:text-ink"
							onClick={onClose}
							type="button"
						>
							<svg
								aria-hidden="true"
								fill="none"
								height="20"
								stroke="currentColor"
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth="2"
								viewBox="0 0 24 24"
								width="20"
							>
								<path d="M18 6 6 18M6 6l12 12" />
							</svg>
						</button>
					</div>

					<div className="mt-4">{children}</div>
				</div>
			</div>
		</dialog>
	);
}
