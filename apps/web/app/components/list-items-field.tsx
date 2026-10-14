import { DragHandle, useDragReorder } from "@components/drag-reorder";

/**
 * One entry of a short list of strings (skills, coursework) while it is being
 * edited. The API stores these as a plain array, so their order is the list's
 * order; `id` only exists to keep React keys stable while rows are dragged
 * around.
 */
export type ListItemDraft = {
	id: string;
	value: string;
};

export function emptyListItem(): ListItemDraft {
	return { id: crypto.randomUUID(), value: "" };
}

/**
 * Converts the API's plain string list back to drafts for editing. A list that
 * needs at least one entry starts with an empty row to type into; an optional
 * one starts empty.
 */
export function fromApiListItems(
	items: string[],
	{ minItems = 1 }: { minItems?: number } = {},
): ListItemDraft[] {
	const drafts = items.map((value) => ({ id: crypto.randomUUID(), value }));
	return drafts.length >= minItems
		? drafts
		: [
				...drafts,
				...Array.from({ length: minItems - drafts.length }, emptyListItem),
			];
}

/** Trims the items and drops the blank ones, preserving the list's order. */
export function toApiListItems(items: ListItemDraft[]): string[] {
	return items
		.map((item) => item.value.trim())
		.filter((value) => value.length > 0);
}

export function ListItemsField({
	error,
	label,
	minItems = 1,
	noun,
	onChange,
	placeholder,
	value,
}: {
	error?: string;
	label: string;
	/** How few rows the list may shrink to; 0 makes the whole list optional. */
	minItems?: number;
	/** What one entry is called, for the row controls' accessible names. */
	noun: string;
	onChange: (items: ListItemDraft[]) => void;
	placeholder: string;
	value: ListItemDraft[];
}) {
	const { getHandleProps, getRowProps, move } = useDragReorder(value, onChange);
	const capitalized = noun.charAt(0).toUpperCase() + noun.slice(1);

	return (
		<div className="flex flex-col gap-2">
			<span className="text-ink-subtle text-sm">{label}</span>

			<ul className="flex flex-col gap-2">
				{value.map((item, index) => (
					<li
						key={item.id}
						{...getRowProps(
							index,
							"flex items-center gap-2 rounded-xl border border-border p-2 transition-opacity",
						)}
					>
						<DragHandle
							label={`Reorder ${noun} ${index + 1}`}
							{...getHandleProps(index)}
						/>
						<input
							aria-label={`${capitalized} ${index + 1}`}
							className="w-full rounded-xl border border-border bg-field px-4 py-field text-ink outline-none transition-colors placeholder:text-ink-disabled focus:border-stroke"
							onChange={(event) =>
								onChange(
									value.map((current) =>
										current.id === item.id
											? { ...current, value: event.target.value }
											: current,
									),
								)
							}
							placeholder={placeholder}
							value={item.value}
						/>
						<button
							aria-label={`Move ${noun} ${index + 1} up`}
							className="rounded-button px-2 py-1 text-ink-subtle text-sm transition-opacity hover:opacity-90 disabled:text-ink-disabled"
							disabled={index === 0}
							onClick={() => move(index, -1)}
							type="button"
						>
							↑
						</button>
						<button
							aria-label={`Move ${noun} ${index + 1} down`}
							className="rounded-button px-2 py-1 text-ink-subtle text-sm transition-opacity hover:opacity-90 disabled:text-ink-disabled"
							disabled={index === value.length - 1}
							onClick={() => move(index, 1)}
							type="button"
						>
							↓
						</button>
						<button
							aria-label={`Remove ${noun} ${index + 1}`}
							className="rounded-button px-3 py-1 text-ink-subtle text-sm transition-opacity hover:opacity-90 disabled:text-ink-disabled"
							disabled={value.length <= minItems}
							onClick={() =>
								onChange(value.filter((current) => current.id !== item.id))
							}
							type="button"
						>
							Remove
						</button>
					</li>
				))}
			</ul>

			{error !== undefined && <p className="text-negative text-sm">{error}</p>}

			<button
				aria-label={`Add ${noun}`}
				className="self-start rounded-button border border-btn-secondary-border px-3 py-1 text-btn-secondary-fg text-sm transition-opacity hover:opacity-90"
				onClick={() => onChange([...value, emptyListItem()])}
				type="button"
			>
				+
			</button>
		</div>
	);
}
