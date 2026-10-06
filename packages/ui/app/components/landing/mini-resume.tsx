/**
 * A resume in miniature, drawn in HTML for the landing page's demos.
 *
 * It is not the product's output — that is a PDF from pdfTeX — but it is laid
 * out after the same template, so the demos read as the thing they describe.
 * Type is sized in container units, so the page scales as a whole wherever it
 * is placed instead of reflowing into something no resume looks like.
 *
 * Every entry in the library is always rendered, and the ones a resume leaves
 * out are collapsed to nothing. That is what lets an entry arrive or leave
 * with a transition rather than popping, without any presence bookkeeping.
 */

import type { ReactNode } from "react";
import {
	DEMO_CONTACT,
	DEMO_LIBRARY,
	DEMO_NAME,
	DEMO_TITLES,
	type DemoEntry,
	type DemoType,
} from "./demo-data";
import type { Flip } from "./motion";

const TYPES: DemoType[] = ["experience", "project", "education", "skill"];

/** Folds to zero height and fades; opens back out to its content. */
function Collapse({
	open,
	children,
	flipRef,
}: {
	open: boolean;
	children: ReactNode;
	flipRef?: (node: HTMLElement | null) => void;
}) {
	return (
		<div
			aria-hidden={!open}
			className={[
				"grid transition-[grid-template-rows,opacity] duration-500 ease-[cubic-bezier(0.2,0,0,1)] motion-reduce:transition-none",
				open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
			].join(" ")}
			ref={flipRef}
		>
			<div className="min-h-0 overflow-hidden">{children}</div>
		</div>
	);
}

function EntryBody({ entry }: { entry: DemoEntry }) {
	if (entry.type === "skill") {
		return (
			<p className="text-[0.92em]">
				<span className="font-bold">{entry.title}:</span> {entry.subtitle}
			</p>
		);
	}

	if (entry.type === "project") {
		return (
			<>
				<p>
					<span className="font-bold">{entry.title}</span>
					<span className="px-[0.4em]">|</span>
					<span className="italic">{entry.subtitle}</span>
				</p>
				<Bullets bullets={entry.bullets} />
			</>
		);
	}

	return (
		<>
			<p className="flex justify-between gap-[1em]">
				<span className="font-bold">{entry.title}</span>
				<span className="shrink-0">{entry.dates}</span>
			</p>
			<p className="italic">{entry.subtitle}</p>
			<Bullets bullets={entry.bullets} />
		</>
	);
}

function Bullets({ bullets }: { bullets: string[] }) {
	if (bullets.length === 0) {
		return null;
	}

	return (
		<ul className="mt-[0.15em] list-disc pl-[1.5em] text-[0.9em]">
			{bullets.map((bullet) => (
				<li key={bullet}>{bullet}</li>
			))}
		</ul>
	);
}

export function MiniResume({
	order,
	entries,
	library = DEMO_LIBRARY,
	highlight = null,
	flip,
	label,
}: {
	/** Which headings print, top to bottom. */
	order: DemoType[];
	/** Attached entry ids, in print order. */
	entries: string[];
	library?: DemoEntry[];
	/** An entry to pick out, as the library does when you point at one. */
	highlight?: string | null;
	flip?: Flip;
	label: string;
}) {
	const byId = new Map(library.map((entry) => [entry.id, entry]));
	const attached = new Set(entries);

	// the headings a resume leaves out still render, folded, after the rest
	const types = [...order, ...TYPES.filter((type) => !order.includes(type))];

	return (
		<figure
			aria-label={label}
			className="@container w-full rounded-md border border-border bg-white text-[#1d1d1b] shadow-raised"
		>
			<div
				className="aspect-[17/22] px-[7%] py-[7%] font-serif leading-[1.3]"
				style={{ fontSize: "max(2.55cqw, 7px)" }}
			>
				<header className="text-center">
					<p className="text-[2.1em] leading-none tracking-tight">
						{DEMO_NAME}
					</p>
					<p className="mt-[0.5em] text-[0.82em]">{DEMO_CONTACT}</p>
				</header>

				{types.map((type) => {
					const shown = entries
						.map((id) => byId.get(id))
						.filter((entry): entry is DemoEntry => entry?.type === type);
					const hidden = library.filter(
						(entry) => entry.type === type && !attached.has(entry.id),
					);
					const open = order.includes(type) && shown.length > 0;

					return (
						<Collapse
							flipRef={flip?.register(`section:${type}`)}
							key={type}
							open={open}
						>
							<section className="pt-[0.9em]">
								<h3 className="border-[#1d1d1b] border-b pb-[0.1em] font-bold text-[1.15em] [font-variant:small-caps]">
									{DEMO_TITLES[type].toLowerCase()}
								</h3>

								{[...shown, ...hidden].map((entry) => (
									<Collapse
										flipRef={flip?.register(
											`entry:${entry.id}`,
											`section:${type}`,
										)}
										key={entry.id}
										open={attached.has(entry.id)}
									>
										<div className="pt-[0.45em]">
											<div
												className={[
													"-mx-[0.4em] rounded-[0.35em] px-[0.4em] py-[0.1em] transition-colors duration-300",
													highlight === entry.id
														? "bg-brand-blue-100"
														: "bg-transparent",
												].join(" ")}
											>
												<EntryBody entry={entry} />
											</div>
										</div>
									</Collapse>
								))}
							</section>
						</Collapse>
					);
				})}
			</div>
		</figure>
	);
}
