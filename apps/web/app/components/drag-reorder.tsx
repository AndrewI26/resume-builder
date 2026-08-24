import { type DragEvent, type KeyboardEvent, useState } from "react";

/** Moves the item at `from` so it lands at `to` in the resulting array. */
export function reorder<T>(items: T[], from: number, to: number): T[] {
	const next = [...items];
	const [moved] = next.splice(from, 1);
	next.splice(to, 0, moved);
	return next;
}

type DropPosition = "above" | "below";

export type RowProps = {
	className: string;
	onDragEnd: () => void;
	onDragOver: (event: DragEvent<HTMLElement>) => void;
	onDrop: (event: DragEvent<HTMLElement>) => void;
};

type HandleProps = {
	draggable: true;
	onDragStart: (event: DragEvent<HTMLElement>) => void;
	onKeyDown: (event: KeyboardEvent<HTMLElement>) => void;
};

/**
 * Drag-to-reorder plumbing for a list whose rows each carry a grab handle.
 * Tracks the row being dragged and where it would land, and returns the props
 * the row and its handle need. Arrow keys on a focused handle move the row as
 * well, so the list is still reorderable without a pointer.
 */
export function useDragReorder<T>(
	items: T[],
	onChange: (next: T[]) => void,
): {
	getHandleProps: (index: number) => HandleProps;
	getRowProps: (index: number, className: string) => RowProps;
	move: (from: number, offset: number) => void;
} {
	const [dragIndex, setDragIndex] = useState<number | null>(null);
	const [dropTarget, setDropTarget] = useState<{
		index: number;
		position: DropPosition;
	} | null>(null);

	const clearDrag = () => {
		setDragIndex(null);
		setDropTarget(null);
	};

	const move = (from: number, offset: number) => {
		const to = from + offset;

		if (to < 0 || to >= items.length) {
			return;
		}

		onChange(reorder(items, from, to));
	};

	const commitDrop = () => {
		if (dragIndex === null || dropTarget === null) {
			clearDrag();
			return;
		}

		// Convert the "above/below row N" hint into a destination index, accounting
		// for the dragged row being lifted out of the list first.
		const insertAt =
			dropTarget.position === "above" ? dropTarget.index : dropTarget.index + 1;
		const to = insertAt > dragIndex ? insertAt - 1 : insertAt;

		if (to !== dragIndex) {
			onChange(reorder(items, dragIndex, to));
		}

		clearDrag();
	};

	const getRowProps = (index: number, className: string): RowProps => {
		const dropPosition =
			dropTarget?.index === index && dragIndex !== index
				? dropTarget.position
				: null;

		return {
			className: [
				className,
				dropPosition === "above" ? "border-t-2 border-t-stroke" : "",
				dropPosition === "below" ? "border-b-2 border-b-stroke" : "",
				dragIndex === index ? "opacity-50" : "",
			]
				.filter(Boolean)
				.join(" "),
			onDragEnd: clearDrag,
			onDragOver: (event) => {
				event.preventDefault();
				const bounds = event.currentTarget.getBoundingClientRect();
				const isAbove = event.clientY < bounds.top + bounds.height / 2;
				setDropTarget({ index, position: isAbove ? "above" : "below" });
			},
			onDrop: (event) => {
				event.preventDefault();
				commitDrop();
			},
		};
	};

	const getHandleProps = (index: number): HandleProps => ({
		draggable: true,
		onDragStart: (event) => {
			// Firefox only starts a drag when some data is set.
			event.dataTransfer.setData("text/plain", String(index));
			event.dataTransfer.effectAllowed = "move";
			setDragIndex(index);
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
