/**
 * "Define it once": one library, two resumes that point into it.
 *
 * Picking an entry lights it up on every resume that uses it, and editing its
 * title rewrites all of them at once — because neither holds a copy. Left
 * alone, the demo walks the library and types an edit itself.
 */

import { useEffect, useRef, useState } from "react";
import { DEMO_LIBRARY, DEMO_TITLES, DEMO_VERSIONS } from "./demo-data";
import { DemoFrame } from "./demo-frame";
import { MiniResume } from "./mini-resume";
import { useAutoplay } from "./motion";

const RESUMES = DEMO_VERSIONS.slice(0, 2);

/** What the demo does on each tick when it is playing itself. */
const SCRIPT: { select: string; title?: string }[] = [
	{ select: "lumen" },
	{ select: "lumen", title: "Senior Frontend Developer" },
	{ select: "brightline" },
	{ select: "waterloo" },
	{ select: "transit" },
	{ select: "lumen", title: "Frontend Developer" },
];

/**
 * One keystroke from `current` towards `target`, editing only the part that
 * differs — so "Frontend Developer" becomes "Senior Frontend Developer" by
 * typing at the front, the way a person would, rather than retyping it all.
 */
function keystroke(current: string, target: string): string {
	let prefix = 0;
	while (
		prefix < current.length &&
		prefix < target.length &&
		current[prefix] === target[prefix]
	) {
		prefix += 1;
	}

	let suffix = 0;
	while (
		suffix < current.length - prefix &&
		suffix < target.length - prefix &&
		current[current.length - 1 - suffix] === target[target.length - 1 - suffix]
	) {
		suffix += 1;
	}

	const head = current.slice(0, prefix);
	const tail = current.slice(current.length - suffix);
	const middle = current.slice(prefix, current.length - suffix);
	const wanted = target.slice(prefix, target.length - suffix);

	if (middle.length > 0) {
		return head + middle.slice(0, -1) + tail;
	}
	return head + wanted.slice(0, 1) + tail;
}

export function ReuseDemo() {
	const frame = useRef<HTMLDivElement>(null);
	const [titles, setTitles] = useState<Record<string, string>>({});
	const [selected, setSelected] = useState("lumen");
	const [typingTo, setTypingTo] = useState<string | null>(null);
	const step = useRef(0);

	const library = DEMO_LIBRARY.map((entry) => ({
		...entry,
		title: titles[entry.id] ?? entry.title,
	}));
	const current = library.find((entry) => entry.id === selected);

	const { playing, play, stop } = useAutoplay(frame, 2600, () => {
		const next = SCRIPT[step.current % SCRIPT.length];
		step.current += 1;
		setSelected(next.select);
		setTypingTo(next.title ?? null);
	});

	// the scripted edit, one character at a time, until it reads as intended
	const typingTitle = current?.title;
	useEffect(() => {
		if (typingTo === null || typingTitle === undefined) {
			return;
		}
		if (typingTitle === typingTo) {
			setTypingTo(null);
			return;
		}

		const id = window.setTimeout(() => {
			setTitles((all) => ({
				...all,
				[selected]: keystroke(typingTitle, typingTo),
			}));
		}, 55);
		return () => window.clearTimeout(id);
	}, [typingTo, typingTitle, selected]);

	const takeOver = () => {
		stop();
		setTypingTo(null);
	};

	return (
		<DemoFrame
			frameRef={frame}
			hint="Pick an entry, then rename it."
			onPlay={play}
			onStop={takeOver}
			playing={playing}
		>
			<div className="grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
				<div>
					<p className="text-sm text-ink-subtle uppercase tracking-increased">
						Library
					</p>

					<ul className="mt-3 divide-y divide-border overflow-hidden rounded-table border border-table-border bg-table">
						{library.map((entry) => {
							const usedIn = RESUMES.filter((resume) =>
								resume.entries.includes(entry.id),
							);
							const active = entry.id === selected;

							return (
								<li key={entry.id}>
									<button
										aria-pressed={active}
										className={[
											"flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors",
											active
												? "bg-table-row-hover"
												: "hover:bg-table-row-hover",
										].join(" ")}
										onClick={() => setSelected(entry.id)}
										type="button"
									>
										<span className="min-w-0">
											<span className="block truncate">{entry.title}</span>
											<span className="block truncate text-ink-subtle text-sm">
												{DEMO_TITLES[entry.type]} · {entry.subtitle}
											</span>
										</span>
										<span
											className={[
												"shrink-0 rounded-button px-2.5 py-1 text-xs transition-colors",
												active
													? "bg-informative-bg text-informative"
													: "bg-btn-tertiary text-ink-subtle",
											].join(" ")}
										>
											{usedIn.length === 0
												? "Unused"
												: `In ${usedIn.length} resume${usedIn.length === 1 ? "" : "s"}`}
										</span>
									</button>
								</li>
							);
						})}
					</ul>

					{current && (
						<label className="mt-5 block">
							<span className="text-ink-subtle text-sm">
								Title of the selected entry
							</span>
							<input
								className="mt-2 w-full rounded-xl border border-border bg-field px-3 py-field outline-none transition-colors focus:border-stroke"
								onChange={(event) =>
									setTitles((all) => ({
										...all,
										[current.id]: event.target.value,
									}))
								}
								value={current.title}
							/>
						</label>
					)}
				</div>

				<div className="grid grid-cols-2 gap-3 sm:gap-5">
					{RESUMES.map((resume) => (
						<div key={resume.id}>
							<p className="mb-3 text-ink-subtle text-sm">
								{resume.name} resume
							</p>
							<MiniResume
								entries={resume.entries}
								highlight={selected}
								label={`The ${resume.name} resume`}
								library={library}
								order={resume.order}
							/>
						</div>
					))}
				</div>
			</div>
		</DemoFrame>
	);
}
