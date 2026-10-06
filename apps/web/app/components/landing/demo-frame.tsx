import type { ReactNode, RefObject } from "react";

/**
 * The card a demo sits in, with the one control every demo needs.
 *
 * Anything that moves by itself for more than a few seconds has to be
 * pausable, so the play button is not optional. It sits outside the area that
 * counts as taking over, so pressing it does not also stop what it starts.
 */
export function DemoFrame({
	frameRef,
	hint,
	playing,
	onPlay,
	onStop,
	children,
}: {
	frameRef: RefObject<HTMLDivElement | null>;
	hint: string;
	playing: boolean;
	onPlay: () => void;
	onStop: () => void;
	children: ReactNode;
}) {
	return (
		<div
			className="rounded-card border border-border bg-card p-4 shadow-raised sm:p-8"
			ref={frameRef}
		>
			<div className="mb-6 flex items-center justify-between gap-4">
				<p className="text-ink-subtle text-sm">{hint}</p>
				<button
					aria-label={playing ? "Pause the demo" : "Play the demo"}
					className="inline-flex h-8 shrink-0 items-center gap-2 rounded-button bg-btn-tertiary px-3 text-btn-tertiary-fg text-sm transition-opacity hover:opacity-90"
					onClick={playing ? onStop : onPlay}
					type="button"
				>
					<svg
						aria-hidden="true"
						fill="currentColor"
						height="10"
						viewBox="0 0 10 10"
						width="10"
					>
						{playing ? (
							<path d="M1.5 1h2.5v8H1.5zM6 1h2.5v8H6z" />
						) : (
							<path d="M2 1l7 4-7 4z" />
						)}
					</svg>
					<span className="text-trim">{playing ? "Pause" : "Play"}</span>
				</button>
			</div>

			{/* any press or key inside the demo itself hands it to the visitor */}
			<div onKeyDownCapture={onStop} onPointerDownCapture={onStop}>
				{children}
			</div>
		</div>
	);
}
