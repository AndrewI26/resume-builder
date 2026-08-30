import { DragHandle, useDragReorder } from "@components/drag-reorder";

/**
 * One skill while it is being edited. The API stores items as a plain array, so
 * their order is the list's order; `id` only exists to keep React keys stable
 * while rows are dragged around.
 */
export type SkillItemDraft = {
	id: string;
	value: string;
};

export function emptySkillItem(): SkillItemDraft {
	return { id: crypto.randomUUID(), value: "" };
}

/** Converts the API's plain string list back to drafts for editing. */
export function fromApiSkillItems(items: string[]): SkillItemDraft[] {
	const drafts = items.map((value) => ({ id: crypto.randomUUID(), value }));
	return drafts.length > 0 ? drafts : [emptySkillItem()];
}

/** Trims the items and drops the blank ones, preserving the list's order. */
export function toApiSkillItems(items: SkillItemDraft[]): string[] {
	return items
		.map((item) => item.value.trim())
		.filter((value) => value.length > 0);
}

export function SkillItemsField({
	error,
	label,
	onChange,
	value,
}: {
	error?: string;
	label: string;
	onChange: (items: SkillItemDraft[]) => void;
	value: SkillItemDraft[];
}) {
	const { getHandleProps, getRowProps, move } = useDragReorder(value, onChange);

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
							label={`Reorder skill ${index + 1}`}
							{...getHandleProps(index)}
						/>
						<input
							aria-label={`Skill ${index + 1}`}
							className="w-full rounded-xl border border-border bg-field px-4 py-2 text-ink outline-none transition-colors placeholder:text-ink-disabled focus:border-stroke"
							onChange={(event) =>
								onChange(
									value.map((current) =>
										current.id === item.id
											? { ...current, value: event.target.value }
											: current,
									),
								)
							}
							placeholder="Python"
							value={item.value}
						/>
						<button
							aria-label={`Move skill ${index + 1} up`}
							className="rounded-button px-2 py-1 text-ink-subtle text-sm transition-opacity hover:opacity-90 disabled:text-ink-disabled"
							disabled={index === 0}
							onClick={() => move(index, -1)}
							type="button"
						>
							↑
						</button>
						<button
							aria-label={`Move skill ${index + 1} down`}
							className="rounded-button px-2 py-1 text-ink-subtle text-sm transition-opacity hover:opacity-90 disabled:text-ink-disabled"
							disabled={index === value.length - 1}
							onClick={() => move(index, 1)}
							type="button"
						>
							↓
						</button>
						<button
							aria-label={`Remove skill ${index + 1}`}
							className="rounded-button px-3 py-1 text-ink-subtle text-sm transition-opacity hover:opacity-90 disabled:text-ink-disabled"
							disabled={value.length === 1}
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
				aria-label="Add skill"
				className="self-start rounded-button border border-btn-secondary-border px-3 py-1 text-btn-secondary-fg text-sm transition-opacity hover:opacity-90"
				onClick={() => onChange([...value, emptySkillItem()])}
				type="button"
			>
				+
			</button>
		</div>
	);
}
