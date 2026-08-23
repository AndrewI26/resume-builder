import {
	DragHandle,
	type RowProps,
	useDragReorder,
} from "@components/drag-reorder";
import { type ComponentProps, useRef } from "react";

/**
 * A bullet point while it is being edited. `bolded` holds half-open [start, end)
 * ranges over `text`; the API wants inclusive ends, so `toApiBulletPoints`
 * converts on the way out. Ranges are always sorted and non-overlapping.
 */
export type BulletPointDraft = {
	id: string;
	text: string;
	bolded: [number, number][];
};

export function emptyBulletPoint(): BulletPointDraft {
	return { id: crypto.randomUUID(), text: "", bolded: [] };
}

/** Drops blank bullets and converts half-open ranges to the API's inclusive ends. */
export function toApiBulletPoints(
	bullets: BulletPointDraft[],
): { text: string; bolded: [number, number][] }[] {
	return bullets
		.map((bullet) => ({ ...bullet, text: bullet.text.trim() }))
		.filter((bullet) => bullet.text.length > 0)
		.map((bullet) => ({
			text: bullet.text,
			bolded: clampRanges(bullet.bolded, bullet.text.length).map(
				([start, end]) => [start, end - 1] as [number, number],
			),
		}));
}

/** Sorts, merges touching/overlapping ranges, and drops empty ones. */
function normalizeRanges(ranges: [number, number][]): [number, number][] {
	const sorted = ranges
		.filter(([start, end]) => end > start)
		.sort((a, b) => a[0] - b[0]);
	const merged: [number, number][] = [];

	for (const [start, end] of sorted) {
		const previous = merged.at(-1);

		if (previous !== undefined && start <= previous[1]) {
			previous[1] = Math.max(previous[1], end);
		} else {
			merged.push([start, end]);
		}
	}

	return merged;
}

function clampRanges(
	ranges: [number, number][],
	length: number,
): [number, number][] {
	return normalizeRanges(
		ranges.map(
			([start, end]) =>
				[
					Math.max(0, Math.min(start, length)),
					Math.max(0, Math.min(end, length)),
				] as [number, number],
		),
	);
}

function toggleBold(
	ranges: [number, number][],
	selectionStart: number,
	selectionEnd: number,
): [number, number][] {
	const existing = normalizeRanges(ranges);
	const alreadyBold = existing.some(
		([start, end]) => start <= selectionStart && end >= selectionEnd,
	);

	if (!alreadyBold) {
		return normalizeRanges([...existing, [selectionStart, selectionEnd]]);
	}

	// Unbold: subtract the selection from every overlapping range.
	return normalizeRanges(
		existing.flatMap(([start, end]): [number, number][] => {
			if (end <= selectionStart || start >= selectionEnd) {
				return [[start, end]];
			}

			return [
				[start, Math.min(end, selectionStart)] as [number, number],
				[Math.max(start, selectionEnd), end] as [number, number],
			].filter(([rangeStart, rangeEnd]) => rangeEnd > rangeStart);
		}),
	);
}

/**
 * Keeps bold ranges attached to their words when the text is edited, by finding
 * the unchanged prefix/suffix around the edit and shifting anything after it.
 * Text inside the edited span collapses to the edit point.
 */
function remapRanges(
	previousText: string,
	nextText: string,
	ranges: [number, number][],
): [number, number][] {
	if (previousText === nextText) {
		return ranges;
	}

	const maxPrefix = Math.min(previousText.length, nextText.length);
	let prefix = 0;
	while (prefix < maxPrefix && previousText[prefix] === nextText[prefix]) {
		prefix += 1;
	}

	let suffix = 0;
	while (
		suffix < maxPrefix - prefix &&
		previousText[previousText.length - 1 - suffix] ===
			nextText[nextText.length - 1 - suffix]
	) {
		suffix += 1;
	}

	const previousEditEnd = previousText.length - suffix;
	const delta = nextText.length - previousText.length;

	const moveIndex = (index: number) => {
		if (index <= prefix) {
			return index;
		}

		if (index >= previousEditEnd) {
			return index + delta;
		}

		return prefix;
	};

	return clampRanges(
		ranges.map(
			([start, end]) => [moveIndex(start), moveIndex(end)] as [number, number],
		),
		nextText.length,
	);
}

/** Splits text into consecutive plain/bold segments for the preview. */
function toSegments(
	text: string,
	ranges: [number, number][],
): { text: string; bold: boolean }[] {
	const segments: { text: string; bold: boolean }[] = [];
	let cursor = 0;

	for (const [start, end] of clampRanges(ranges, text.length)) {
		if (start > cursor) {
			segments.push({ text: text.slice(cursor, start), bold: false });
		}

		segments.push({ text: text.slice(start, end), bold: true });
		cursor = end;
	}

	if (cursor < text.length) {
		segments.push({ text: text.slice(cursor), bold: false });
	}

	return segments;
}

function BulletRow({
	bullet,
	canRemove,
	handleProps,
	index,
	onChange,
	onRemove,
	rowProps,
}: {
	bullet: BulletPointDraft;
	canRemove: boolean;
	handleProps: ComponentProps<typeof DragHandle>;
	index: number;
	onChange: (bullet: BulletPointDraft) => void;
	onRemove: () => void;
	rowProps: RowProps;
}) {
	const inputRef = useRef<HTMLTextAreaElement>(null);
	// Mirrors the input's live selection so the Bold button still knows what was
	// highlighted after the button steals focus.
	const selectionRef = useRef<[number, number]>([0, 0]);

	const rememberSelection = () => {
		const input = inputRef.current;

		if (input !== null) {
			selectionRef.current = [input.selectionStart, input.selectionEnd];
		}
	};

	const applyBold = () => {
		const [start, end] = selectionRef.current;

		if (end <= start) {
			return;
		}

		onChange({ ...bullet, bolded: toggleBold(bullet.bolded, start, end) });
		inputRef.current?.focus();
		requestAnimationFrame(() =>
			inputRef.current?.setSelectionRange(start, end),
		);
	};

	const segments = toSegments(bullet.text, bullet.bolded);

	return (
		<li {...rowProps}>
			<div className="flex items-start gap-2">
				<DragHandle {...handleProps} />
				<textarea
					aria-label={`Bullet point ${index + 1}`}
					className="min-h-16 w-full rounded-xl border border-border bg-field px-4 py-2 text-ink outline-none transition-colors placeholder:text-ink-disabled focus:border-stroke"
					onChange={(event) =>
						onChange({
							...bullet,
							text: event.target.value,
							bolded: remapRanges(
								bullet.text,
								event.target.value,
								bullet.bolded,
							),
						})
					}
					onKeyDown={(event) => {
						if ((event.metaKey || event.ctrlKey) && event.key === "b") {
							event.preventDefault();
							rememberSelection();
							applyBold();
						}
					}}
					onKeyUp={rememberSelection}
					onMouseUp={rememberSelection}
					onSelect={rememberSelection}
					placeholder="Cut p99 latency by 40% by adding a read-through cache"
					ref={inputRef}
					value={bullet.text}
				/>
			</div>

			<div className="flex items-center gap-2">
				<button
					className="rounded-button border border-btn-secondary-border px-3 py-1 font-semibold text-btn-secondary-fg text-sm transition-opacity hover:opacity-90"
					onClick={applyBold}
					// Keeps the textarea's selection intact when the button is pressed.
					onMouseDown={(event) => event.preventDefault()}
					title="Bold the selected text (⌘B)"
					type="button"
				>
					B
				</button>
				<span className="text-ink-subtle text-xs">
					Select text, then Bold (⌘B)
				</span>
				<button
					aria-label={`Remove bullet point ${index + 1}`}
					className="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-full bg-btn-warning text-btn-warning-fg transition-opacity hover:opacity-90 disabled:bg-disabled disabled:text-ink-disabled"
					disabled={!canRemove}
					onClick={onRemove}
					type="button"
				>
					<svg
						aria-hidden="true"
						fill="none"
						height="16"
						stroke="currentColor"
						strokeLinecap="round"
						strokeLinejoin="round"
						strokeWidth="2"
						viewBox="0 0 24 24"
						width="16"
					>
						<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6" />
						<path d="M10 11v6M14 11v6" />
					</svg>
				</button>
			</div>

			{segments.length > 0 && (
				<p className="text-ink-subtle text-sm">
					{segments.map((segment, segmentIndex) => (
						<span
							className={segment.bold ? "font-semibold text-ink" : undefined}
							// biome-ignore lint/suspicious/noArrayIndexKey: segments are positional
							key={segmentIndex}
						>
							{segment.text}
						</span>
					))}
				</p>
			)}
		</li>
	);
}

export function BulletPointsField({
	label,
	onChange,
	value,
}: {
	label: string;
	onChange: (bullets: BulletPointDraft[]) => void;
	value: BulletPointDraft[];
}) {
	const { getHandleProps, getRowProps } = useDragReorder(value, onChange);

	return (
		<div className="flex flex-col gap-2">
			<span className="text-ink-subtle text-sm">{label}</span>

			<ul className="flex flex-col gap-2">
				{value.map((bullet, index) => (
					<BulletRow
						bullet={bullet}
						canRemove={value.length > 1}
						handleProps={{
							label: `Reorder bullet point ${index + 1}`,
							...getHandleProps(index),
						}}
						index={index}
						key={bullet.id}
						onChange={(next) =>
							onChange(value.map((item) => (item.id === next.id ? next : item)))
						}
						onRemove={() =>
							onChange(value.filter((item) => item.id !== bullet.id))
						}
						rowProps={getRowProps(
							index,
							"flex flex-col gap-2 rounded-xl border border-border p-3 transition-opacity",
						)}
					/>
				))}
			</ul>

			<button
				className="self-start rounded-button border border-btn-secondary-border px-3 py-1 text-btn-secondary-fg text-sm transition-opacity hover:opacity-90"
				onClick={() => onChange([...value, emptyBulletPoint()])}
				type="button"
			>
				+
			</button>
		</div>
	);
}
