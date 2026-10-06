/**
 * "Put it in any order": the headings of a resume, dragged into place.
 *
 * The list on the left is the editor's own drag-to-reorder, and the page
 * beside it follows each move. Left alone, it reshuffles itself into the
 * orders a real person might want: experience first, education first for a
 * new grad, skills first for a recruiter skimming.
 */

import { DragHandle, useDragReorder } from "@components/drag-reorder";
import { useRef, useState } from "react";
import { DEMO_TITLES, DEMO_VERSIONS, type DemoType } from "./demo-data";
import { DemoFrame } from "./demo-frame";
import { MiniResume } from "./mini-resume";
import { useAutoplay, useFlip } from "./motion";

const ENTRIES = DEMO_VERSIONS[0].entries;

const ORDERS: DemoType[][] = [
	["experience", "project", "skill", "education"],
	["education", "experience", "project", "skill"],
	["skill", "experience", "project", "education"],
	["project", "experience", "education", "skill"],
];

export function ReorderDemo() {
	const frame = useRef<HTMLDivElement>(null);
	const [order, setOrder] = useState<DemoType[]>(ORDERS[0]);
	const step = useRef(1);

	const page = useFlip();
	const list = useFlip(360);

	// A drop needs no animation in the list — the rows are already where
	// they land, and the drag hook settles them itself — but a key press or
	// a scripted move does, or the list would teleport beside a page that
	// glides.
	const fromPointer = useRef(false);

	const change = (next: DemoType[]) => {
		page.capture();
		if (!fromPointer.current) {
			list.capture();
		}
		fromPointer.current = false;
		setOrder(next);
	};

	const { getHandleProps, getRowProps, move } = useDragReorder(order, change);

	const { playing, play, stop } = useAutoplay(frame, 2400, () => {
		change(ORDERS[step.current % ORDERS.length]);
		step.current += 1;
	});

	return (
		<DemoFrame
			frameRef={frame}
			hint="Drag a heading, or focus one and use ↑ / ↓."
			onPlay={play}
			onStop={stop}
			playing={playing}
		>
			<div className="grid grid-cols-[minmax(0,1fr)] items-start gap-8 md:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-16">
				<div>
					<p className="text-sm text-ink-subtle uppercase tracking-increased">
						Section order
					</p>

					<ul className="mt-3 flex flex-col gap-2">
						{order.map((type, index) => {
							const handle = getHandleProps(index);
							const row = getRowProps(
								index,
								"flex items-center gap-2 rounded-2xl border border-border bg-card-primary py-2 pr-3 pl-1",
							);
							const flipRef = list.register(type);

							return (
								<li
									className={row.className}
									key={type}
									ref={(node) => {
										row.ref(node);
										flipRef(node);
									}}
									style={row.style}
								>
									<DragHandle
										label={`Reorder ${DEMO_TITLES[type]}`}
										{...handle}
										onPointerDown={(event) => {
											fromPointer.current = true;
											handle.onPointerDown(event);
										}}
									/>
									<span className="flex-1 text-trim">{DEMO_TITLES[type]}</span>
									<span className="flex">
										<button
											aria-label={`Move ${DEMO_TITLES[type]} up`}
											className="px-1.5 text-ink-subtle enabled:hover:text-ink disabled:opacity-30"
											disabled={index === 0}
											onClick={() => move(index, -1)}
											type="button"
										>
											↑
										</button>
										<button
											aria-label={`Move ${DEMO_TITLES[type]} down`}
											className="px-1.5 text-ink-subtle enabled:hover:text-ink disabled:opacity-30"
											disabled={index === order.length - 1}
											onClick={() => move(index, 1)}
											type="button"
										>
											↓
										</button>
									</span>
								</li>
							);
						})}
					</ul>

					<p className="mt-6 max-w-sm text-ink-subtle text-sm leading-body">
						The order belongs to the resume, not the library — so moving
						Education up here leaves every other resume as it was.
					</p>
				</div>

				<div className="mx-auto w-full max-w-md">
					<MiniResume
						entries={ENTRIES}
						flip={page}
						label="A resume whose sections follow the order on the left"
						order={order}
					/>
				</div>
			</div>
		</DemoFrame>
	);
}
