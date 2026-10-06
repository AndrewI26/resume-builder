/**
 * "A version for every application": one page, three resumes.
 *
 * Switching version re-picks entries from the same library and re-orders the
 * headings, and the page moves to match — rows fold away, others open, whole
 * sections change places. The checklist edits the version on screen and only
 * that one, which is the promise the product makes.
 */

import { useRef, useState } from "react";
import {
	DEMO_LIBRARY,
	DEMO_TITLES,
	DEMO_VERSIONS,
	type DemoType,
	type DemoVersion,
} from "./demo-data";
import { DemoFrame } from "./demo-frame";
import { MiniResume } from "./mini-resume";
import { useAutoplay, useFlip } from "./motion";

const GROUPS: DemoType[] = ["experience", "project", "education", "skill"];

export function VersionsDemo() {
	const frame = useRef<HTMLDivElement>(null);
	const [versions, setVersions] = useState<DemoVersion[]>(DEMO_VERSIONS);
	const [activeId, setActiveId] = useState(DEMO_VERSIONS[0].id);
	const page = useFlip();

	const active =
		versions.find((version) => version.id === activeId) ?? versions[0];

	const show = (id: string) => {
		page.capture();
		setActiveId(id);
	};

	const toggle = (entryId: string) => {
		page.capture();
		setVersions((all) =>
			all.map((version) =>
				version.id !== active.id
					? version
					: {
							...version,
							entries: version.entries.includes(entryId)
								? version.entries.filter((id) => id !== entryId)
								: [...version.entries, entryId],
						},
			),
		);
	};

	const { playing, play, stop } = useAutoplay(frame, 3200, () => {
		const index = versions.findIndex((version) => version.id === activeId);
		show(versions[(index + 1) % versions.length].id);
	});

	return (
		<DemoFrame
			frameRef={frame}
			hint="Switch version, or tick entries on and off."
			onPlay={play}
			onStop={stop}
			playing={playing}
		>
			<div className="grid grid-cols-[minmax(0,1fr)] items-start gap-8 md:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-16">
				<div>
					<div
						aria-label="Resume version"
						className="inline-flex rounded-button bg-btn-tertiary p-1"
						role="tablist"
					>
						{versions.map((version) => {
							const selected = version.id === active.id;
							return (
								<button
									aria-selected={selected}
									className={[
										"h-9 rounded-button px-4 text-sm transition-colors duration-300",
										selected
											? "bg-btn-primary text-btn-primary-fg"
											: "text-btn-tertiary-fg hover:text-ink",
									].join(" ")}
									key={version.id}
									onClick={() => show(version.id)}
									role="tab"
									type="button"
								>
									<span className="text-trim">{version.name}</span>
								</button>
							);
						})}
					</div>

					<div className="mt-6 space-y-5">
						{GROUPS.map((type) => (
							<fieldset key={type}>
								<legend className="text-sm text-ink-subtle uppercase tracking-increased">
									{DEMO_TITLES[type]}
								</legend>
								<div className="mt-2 flex flex-wrap gap-2">
									{DEMO_LIBRARY.filter((entry) => entry.type === type).map(
										(entry) => {
											const on = active.entries.includes(entry.id);
											return (
												<label
													className={[
														"inline-flex cursor-pointer items-center gap-2 rounded-button border px-3 py-1.5 text-sm transition-colors duration-300 has-[:focus-visible]:outline-2",
														on
															? "border-stroke bg-btn-primary text-btn-primary-fg"
															: "border-border bg-card-primary text-ink-subtle hover:text-ink",
													].join(" ")}
													key={entry.id}
												>
													<input
														checked={on}
														className="sr-only"
														onChange={() => toggle(entry.id)}
														type="checkbox"
													/>
													<span aria-hidden="true">{on ? "✓" : "+"}</span>
													<span className="text-trim">{entry.title}</span>
												</label>
											);
										},
									)}
								</div>
							</fieldset>
						))}
					</div>
				</div>

				<div className="mx-auto w-full max-w-md">
					<MiniResume
						entries={active.entries}
						flip={page}
						label={`The ${active.name} resume`}
						order={active.order}
					/>
				</div>
			</div>
		</DemoFrame>
	);
}
