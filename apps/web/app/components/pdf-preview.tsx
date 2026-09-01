/**
 * The compiled resume, shown as the PDF it actually is.
 *
 * The browser's own PDF viewer renders it, which is the point: what appears
 * here is the same file that downloads, typeset by the same engine, rather
 * than a likeness of it. The cost is that it cannot update as someone drags a
 * row — a compile is a server round trip — so the page has to say plainly when
 * what is on screen is behind the panel beside it.
 */

import { Button } from "@components/button";

export type PdfState = {
	url: string;
	blob: Blob;
	/** The draft signature this was built from, to notice when it goes stale. */
	signature: string;
};

/**
 * The viewer's own toolbar is left on deliberately.
 *
 * Zooming and panning a PDF is something every browser's viewer already does
 * properly — at the PDF's own resolution, so text stays sharp at any zoom.
 * Hiding it to reach a cleaner frame would mean rebuilding those controls on
 * top of a CSS transform, which only scales an already-rasterised page and
 * comes out soft. `view=FitH` just picks the opening zoom.
 */
function Frame({ url, dimmed }: { url: string; dimmed: boolean }) {
	return (
		<iframe
			src={`${url}#view=FitH`}
			title="Resume preview"
			className={[
				"h-full w-full rounded-xl border border-border bg-white transition-opacity",
				dimmed ? "opacity-40" : "",
			]
				.filter(Boolean)
				.join(" ")}
		/>
	);
}

function Placeholder({ children }: { children: React.ReactNode }) {
	return (
		<div className="flex h-full w-full items-center justify-center rounded-xl border border-border border-dashed">
			<p className="px-6 text-center text-ink-subtle text-sm">{children}</p>
		</div>
	);
}

export function PdfPreview({
	pdf,
	compiling,
	stale,
	error,
	onRecompile,
	onDownload,
}: {
	pdf: PdfState | null;
	compiling: boolean;
	stale: boolean;
	error: string | null;
	onRecompile: () => void;
	onDownload: () => void;
}) {
	return (
		<div className="flex min-h-0 flex-1 flex-col gap-3">
			<div className="flex flex-wrap items-center gap-3">
				<p className="mr-auto text-ink-subtle text-sm">
					{compiling ? (
						"Compiling…"
					) : stale ? (
						<>
							<span className="font-semibold text-ink">Out of date.</span> This
							PDF was built before your latest changes — recompile to see them.
						</>
					) : pdf ? (
						"Compiled from your saved resume."
					) : (
						"Not compiled yet."
					)}
				</p>

				{/* the browser gives a full window far more room to zoom into than
				    a pane beside an editor ever will */}
				<Button
					disabled={pdf === null}
					onClick={() => pdf && window.open(pdf.url, "_blank", "noopener")}
					variant="tertiary"
				>
					Open full size
				</Button>

				<Button disabled={compiling} onClick={onRecompile} variant="secondary">
					{compiling ? "Compiling…" : "Recompile"}
				</Button>

				{/* the blob is already in the page, so this saves it without asking
				    the server to typeset the same document twice */}
				<Button disabled={pdf === null || compiling} onClick={onDownload}>
					Download PDF
				</Button>
			</div>

			{error && (
				<p
					className="max-h-40 overflow-auto whitespace-pre-wrap rounded-xl bg-negative-bg px-4 py-2 font-mono text-negative text-xs"
					role="alert"
				>
					{error}
				</p>
			)}

			{/*
			 * Opens at US Letter proportions so the page is not letterboxed, but
			 * `resize` lets it be dragged taller — useful once someone zooms in
			 * and wants more of the page visible at once.
			 */}
			<div className="aspect-[8.5/11] w-full min-h-[420px] resize-y overflow-hidden">
				{pdf ? (
					<Frame url={pdf.url} dimmed={compiling} />
				) : (
					<Placeholder>
						{compiling
							? "Building the PDF…"
							: error
								? "The last compile failed."
								: "Nothing compiled yet."}
					</Placeholder>
				)}
			</div>
		</div>
	);
}
