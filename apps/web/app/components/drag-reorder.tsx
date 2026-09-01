import {
	type CSSProperties,
	type KeyboardEvent,
	type PointerEvent as ReactPointerEvent,
	useEffect,
	useRef,
	useState,
} from "react";

/** Moves the item at `from` so it lands at `to` in the resulting array. */
export function reorder<T>(items: T[], from: number, to: number): T[] {
	const next = [...items];
	const [moved] = next.splice(from, 1);
	next.splice(to, 0, moved);
	return next;
}

export type RowProps = {
	className: string;
	ref: (node: HTMLLIElement | null) => void;
	style: CSSProperties;
};

type HandleProps = {
	onKeyDown: (event: KeyboardEvent<HTMLElement>) => void;
	onPointerDown: (event: ReactPointerEvent<HTMLElement>) => void;
	style: CSSProperties;
};

/** Where every row sat when the drag began, in page coordinates. */
type Geometry = { tops: number[]; heights: number[]; gap: number };

type Drag = {
	index: number;
	/** Pointer position at grab and now, both in page coordinates. */
	startY: number;
	pointerY: number;
	geometry: Geometry;
};

/** How far the pointer has to be from an edge before the page starts scrolling. */
const SCROLL_MARGIN = 72;
const SCROLL_SPEED = 14;

/**
 * Which slot the dragged row currently occupies.
 *
 * A row passes its neighbour once it has crossed that neighbour's midpoint,
 * which is why the heights are measured rather than assumed: the heading cards
 * are not all the same size, so a fixed step would drift after the first swap.
 */
function targetIndex({ index, startY, pointerY, geometry }: Drag): number {
	const { tops, heights } = geometry;
	const top = tops[index] + (pointerY - startY);
	const bottom = top + heights[index];

	let target = index;
	while (
		target < tops.length - 1 &&
		bottom > tops[target + 1] + heights[target + 1] / 2
	) {
		target += 1;
	}
	while (target > 0 && top < tops[target - 1] + heights[target - 1] / 2) {
		target -= 1;
	}

	return target;
}

/**
 * Drag-to-reorder for a list whose rows each carry a grab handle.
 *
 * The row itself follows the cursor and the rows it passes slide out of its
 * way, so the list shows the result rather than describing it with a marker.
 *
 * Built on pointer events rather than HTML5 drag-and-drop: the native API only
 * offers a browser-drawn ghost that cannot be styled or animated, and its
 * events fire on whatever sits under the cursor, which made nested lists
 * (rows inside a draggable card) fight over the same drag. Here only the list
 * whose handle was pressed has any state at all, so nesting is not a case.
 *
 * Arrow keys on a focused handle move the row too, so the list is still
 * reorderable without a pointer.
 */
export function useDragReorder<T>(
	items: T[],
	onChange: (next: T[]) => void,
): {
	getHandleProps: (index: number) => HandleProps;
	getRowProps: (index: number, className: string) => RowProps;
	move: (from: number, offset: number) => void;
} {
	const [drag, setDrag] = useState<Drag | null>(null);

	const rows = useRef<(HTMLLIElement | null)[]>([]);
	// the window listeners are attached once per drag, so they would otherwise
	// close over the first render's props
	const latest = useRef({ items, onChange, drag });
	latest.current = { items, onChange, drag };

	const move = (from: number, offset: number) => {
		const to = from + offset;

		if (to < 0 || to >= items.length) {
			return;
		}

		onChange(reorder(items, from, to));
	};

	const dragging = drag !== null;

	useEffect(() => {
		if (!dragging) {
			return;
		}

		let pointerViewportY = 0;
		let frame = 0;

		const update = (y: number) => {
			const current = latest.current.drag;
			if (current) {
				setDrag({ ...current, pointerY: y });
			}
		};

		const onMove = (event: PointerEvent) => {
			pointerViewportY = event.clientY;
			update(event.clientY + window.scrollY);
		};

		// the panel is taller than most windows, so a drag has to be able to
		// take the page with it or the far end is unreachable
		const autoScroll = () => {
			const distanceToTop = pointerViewportY;
			const distanceToBottom = window.innerHeight - pointerViewportY;
			const delta =
				distanceToTop < SCROLL_MARGIN
					? -SCROLL_SPEED
					: distanceToBottom < SCROLL_MARGIN
						? SCROLL_SPEED
						: 0;

			if (delta !== 0) {
				const before = window.scrollY;
				window.scrollBy(0, delta);
				if (window.scrollY !== before) {
					update(pointerViewportY + window.scrollY);
				}
			}

			frame = requestAnimationFrame(autoScroll);
		};

		const onEnd = () => {
			const current = latest.current.drag;

			if (current) {
				const to = targetIndex(current);
				if (to !== current.index) {
					latest.current.onChange(
						reorder(latest.current.items, current.index, to),
					);
				}
			}

			setDrag(null);
		};

		frame = requestAnimationFrame(autoScroll);
		window.addEventListener("pointermove", onMove);
		window.addEventListener("pointerup", onEnd);
		window.addEventListener("pointercancel", onEnd);

		// without this the drag paints a text selection across the whole panel
		const previousSelect = document.body.style.userSelect;
		document.body.style.userSelect = "none";

		return () => {
			cancelAnimationFrame(frame);
			window.removeEventListener("pointermove", onMove);
			window.removeEventListener("pointerup", onEnd);
			window.removeEventListener("pointercancel", onEnd);
			document.body.style.userSelect = previousSelect;
		};
	}, [dragging]);

	/** How far this row is displaced from where it was laid out. */
	const offsetFor = (index: number): number => {
		if (drag === null) {
			return 0;
		}

		if (index === drag.index) {
			return drag.pointerY - drag.startY;
		}

		const target = targetIndex(drag);
		const step = drag.geometry.heights[drag.index] + drag.geometry.gap;

		if (target > drag.index && index > drag.index && index <= target) {
			return -step;
		}

		if (target < drag.index && index >= target && index < drag.index) {
			return step;
		}

		return 0;
	};

	const getRowProps = (index: number, className: string): RowProps => {
		const lifted = drag?.index === index;
		const offset = offsetFor(index);

		return {
			className: [
				className,
				lifted
					? "z-10 cursor-grabbing shadow-lg"
					: // the lifted row tracks the cursor exactly; only the rows
						// getting out of its way are worth animating
						"[transition:transform_140ms_ease]",
			].join(" "),
			ref: (node) => {
				rows.current[index] = node;
			},
			style: {
				transform: offset === 0 ? undefined : `translateY(${offset}px)`,
				position: lifted ? "relative" : undefined,
			},
		};
	};

	const getHandleProps = (index: number): HandleProps => ({
		style: { touchAction: "none" },
		onPointerDown: (event) => {
			// only a primary press starts a drag; a right-click or a second
			// finger should not
			if (event.button !== 0) {
				return;
			}

			// a handle belongs to exactly one list, so an inner row's grab must
			// not also reach the card it sits in
			event.stopPropagation();
			event.preventDefault();

			const measured = rows.current.slice(0, items.length);
			if (measured.some((node) => node === null)) {
				return;
			}

			const boxes = measured.map((node) =>
				(node as HTMLLIElement).getBoundingClientRect(),
			);
			const tops = boxes.map((box) => box.top + window.scrollY);
			const heights = boxes.map((box) => box.height);
			const gap =
				boxes.length > 1 ? Math.max(0, tops[1] - (tops[0] + heights[0])) : 0;

			const pointerY = event.clientY + window.scrollY;
			setDrag({
				index,
				startY: pointerY,
				pointerY,
				geometry: { tops, heights, gap },
			});
		},
		onKeyDown: (event) => {
			if (event.key === "ArrowUp") {
				event.preventDefault();
				move(index, -1);
			}

			if (event.key === "ArrowDown") {
				event.preventDefault();
				move(index, 1);
			}
		},
	});

	return { getHandleProps, getRowProps, move };
}

/** The grab handle for one row; spread `getHandleProps(index)` onto it. */
export function DragHandle({
	label,
	...handleProps
}: HandleProps & { label: string }) {
	return (
		<button
			aria-label={label}
			className="cursor-grab rounded-button px-2 py-2 text-ink-subtle transition-opacity hover:opacity-70 active:cursor-grabbing"
			title="Drag to reorder (or focus and use ↑ / ↓)"
			type="button"
			{...handleProps}
		>
			⠿
		</button>
	);
}
