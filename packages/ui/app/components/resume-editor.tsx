/**
 * The editing panel beside the preview.
 *
 * Two orderings are editable and they are not the same thing: the order of the
 * headings down the page, and the order of the rows under one heading. The API
 * keeps them apart — `section_order` on the resume, `position` within a type —
 * so the panel does too rather than flattening them into one list and having
 * to guess which move was meant.
 *
 * Every control changes the caller's draft and nothing else. Persisting is the
 * route's job, which is what lets the preview redraw on each edit without a
 * save in between.
 */

import { Button } from "@components/button";
import { DragHandle, useDragReorder } from "@components/drag-reorder";
import { Dropdown } from "@components/dropdown";
import { useState } from "react";
import {
	attach,
	type Catalogs,
	describe,
	detach,
	findRow,
	moveItem,
	moveWithinType,
	type ResumeDraft,
	refsOfType,
	SECTION_TITLES,
	SECTION_TYPES,
	type SectionRef,
	setTypeOrder,
	swap,
} from "~/lib/resume/document";
import type { SectionType } from "~/lib/resume/types";

function NudgeButtons({
	onUp,
	onDown,
	upDisabled,
	downDisabled,
	label,
}: {
	onUp: () => void;
	onDown: () => void;
	upDisabled: boolean;
	downDisabled: boolean;
	label: string;
}) {
	return (
		<>
			<button
				aria-label={`Move ${label} up`}
				className="px-1 text-ink-subtle enabled:hover:text-ink disabled:opacity-30"
				disabled={upDisabled}
				onClick={onUp}
				type="button"
			>
				↑
			</button>
			<button
				aria-label={`Move ${label} down`}
				className="px-1 text-ink-subtle enabled:hover:text-ink disabled:opacity-30"
				disabled={downDisabled}
				onClick={onDown}
				type="button"
			>
				↓
			</button>
		</>
	);
}

function TrashIcon() {
	return (
		<svg
			aria-hidden="true"
			fill="none"
			height="15"
			stroke="currentColor"
			strokeLinecap="round"
			strokeLinejoin="round"
			strokeWidth="2"
			viewBox="0 0 24 24"
			width="15"
		>
			<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6" />
			<path d="M10 11v6M14 11v6" />
		</svg>
	);
}

/** One attached row: reorder it, swap it for another, or take it off. */
function AttachedRow({
	catalogs,
	draft,
	index,
	onChange,
	refs,
	type,
	rowProps,
	handleProps,
}: {
	catalogs: Catalogs;
	draft: ResumeDraft;
	index: number;
	onChange: (next: ResumeDraft) => void;
	refs: SectionRef[];
	type: SectionType;
	rowProps: ReturnType<ReturnType<typeof useDragReorder>["getRowProps"]>;
	handleProps: ReturnType<ReturnType<typeof useDragReorder>["getHandleProps"]>;
}) {
	const ref = refs[index];
	const row = findRow(catalogs, ref);
	const attachedIds = new Set(refs.map((item) => item.section_id));

	// swapping to something already on the resume would silently drop a row, so
	// the menu offers this row plus whatever is still unused
	const choices = catalogs[type].filter(
		(candidate) =>
			candidate.id === ref.section_id || !attachedIds.has(candidate.id),
	);

	return (
		<li {...rowProps}>
			<DragHandle
				label={`Reorder ${SECTION_TITLES[type]} entry`}
				{...handleProps}
			/>

			{row === undefined ? (
				<span className="flex-1 text-negative text-sm">
					This entry was deleted.
				</span>
			) : (
				<Dropdown
					className="min-w-0 flex-1"
					onChange={(nextId) => onChange(swap(draft, ref, nextId))}
					options={choices.map((candidate) => ({
						value: candidate.id,
						label: describe(type, candidate),
					}))}
					value={ref.section_id}
				/>
			)}

			<span className="flex shrink-0 items-center">
				<NudgeButtons
					downDisabled={index === refs.length - 1}
					label="entry"
					onDown={() => onChange(moveWithinType(draft, type, index, index + 1))}
					onUp={() => onChange(moveWithinType(draft, type, index, index - 1))}
					upDisabled={index === 0}
				/>
				<button
					aria-label={`Remove ${row ? describe(type, row) : "entry"}`}
					className="px-1 text-ink-subtle hover:text-negative"
					onClick={() => onChange(detach(draft, ref))}
					type="button"
				>
					<TrashIcon />
				</button>
			</span>
		</li>
	);
}

/** The rows under one heading, reorderable among themselves. */
function AttachedRows({
	catalogs,
	draft,
	onChange,
	type,
}: {
	catalogs: Catalogs;
	draft: ResumeDraft;
	onChange: (next: ResumeDraft) => void;
	type: SectionType;
}) {
	const refs = refsOfType(draft, type);

	const { getHandleProps, getRowProps } = useDragReorder(refs, (next) =>
		onChange(setTypeOrder(draft, type, next)),
	);

	if (refs.length === 0) {
		return (
			<p className="px-3 py-2 text-ink-subtle text-sm">
				Nothing here yet — this heading will not appear on the resume.
			</p>
		);
	}

	return (
		<ol className="flex flex-col gap-1">
			{refs.map((ref, index) => (
				<AttachedRow
					catalogs={catalogs}
					draft={draft}
					handleProps={getHandleProps(index)}
					index={index}
					key={`${ref.section_type}:${ref.section_id}`}
					onChange={onChange}
					refs={refs}
					rowProps={getRowProps(
						index,
						"flex items-center gap-1 rounded-lg bg-field px-1 py-1",
					)}
					type={type}
				/>
			))}
		</ol>
	);
}

/** Adds one more row of a given type, offering only what is not already on. */
function AddRow({
	catalogs,
	draft,
	onChange,
	type,
}: {
	catalogs: Catalogs;
	draft: ResumeDraft;
	onChange: (next: ResumeDraft) => void;
	type: SectionType;
}) {
	const [choice, setChoice] = useState("");
	const attachedIds = new Set(
		refsOfType(draft, type).map((ref) => ref.section_id),
	);
	const available = catalogs[type].filter((row) => !attachedIds.has(row.id));

	if (available.length === 0) {
		return (
			<p className="mt-2 text-ink-subtle text-xs">
				Everything you have of this type is already on the resume.
			</p>
		);
	}

	return (
		<div className="mt-2 flex items-end gap-2">
			<Dropdown
				className="min-w-0 flex-1"
				onChange={setChoice}
				options={available.map((row) => ({
					value: row.id,
					label: describe(type, row),
				}))}
				placeholder={`Add ${SECTION_TITLES[type].toLowerCase()}…`}
				value={choice}
			/>
			<Button
				disabled={choice === ""}
				onClick={() => {
					onChange(attach(draft, { section_type: type, section_id: choice }));
					setChoice("");
				}}
				variant="secondary"
			>
				Add
			</Button>
		</div>
	);
}

/** One heading: its own place on the page, and the rows under it. */
function HeadingBlock({
	catalogs,
	draft,
	index,
	onChange,
	rowProps,
	handleProps,
	type,
}: {
	catalogs: Catalogs;
	draft: ResumeDraft;
	index: number;
	onChange: (next: ResumeDraft) => void;
	rowProps: ReturnType<ReturnType<typeof useDragReorder>["getRowProps"]>;
	handleProps: ReturnType<ReturnType<typeof useDragReorder>["getHandleProps"]>;
	type: SectionType;
}) {
	const count = refsOfType(draft, type).length;

	const moveHeading = (to: number) =>
		onChange({ ...draft, order: moveItem(draft.order, index, to) });

	return (
		<li {...rowProps}>
			<div className="flex items-center gap-1">
				<DragHandle
					label={`Reorder ${SECTION_TITLES[type]} heading`}
					{...handleProps}
				/>

				<h3 className="mr-auto font-semibold text-sm">
					{SECTION_TITLES[type]}
					<span className="ml-2 font-normal text-ink-subtle text-xs">
						{count === 0
							? "hidden"
							: `${count} ${count === 1 ? "entry" : "entries"}`}
					</span>
				</h3>

				<NudgeButtons
					downDisabled={index === draft.order.length - 1}
					label="heading"
					onDown={() => moveHeading(index + 1)}
					onUp={() => moveHeading(index - 1)}
					upDisabled={index === 0}
				/>
			</div>

			<div className="mt-2">
				<AttachedRows
					catalogs={catalogs}
					draft={draft}
					onChange={onChange}
					type={type}
				/>
				<AddRow
					catalogs={catalogs}
					draft={draft}
					onChange={onChange}
					type={type}
				/>
			</div>
		</li>
	);
}

export function ResumeEditor({
	catalogs,
	draft,
	onChange,
}: {
	catalogs: Catalogs;
	draft: ResumeDraft;
	onChange: (next: ResumeDraft) => void;
}) {
	const { getHandleProps, getRowProps } = useDragReorder(draft.order, (order) =>
		onChange({ ...draft, order }),
	);

	// a type with nothing attached and no heading is still addable, so it needs
	// somewhere to live in the panel
	const unused = SECTION_TYPES.filter((type) => !draft.order.includes(type));

	return (
		<div className="flex flex-col gap-4">
			<ol className="flex flex-col gap-3">
				{draft.order.map((type, index) => (
					<HeadingBlock
						catalogs={catalogs}
						draft={draft}
						handleProps={getHandleProps(index)}
						index={index}
						key={type}
						onChange={onChange}
						rowProps={getRowProps(
							index,
							"rounded-xl border border-border bg-table p-3",
						)}
						type={type}
					/>
				))}
			</ol>

			{unused.length > 0 && (
				<div className="rounded-xl border border-border border-dashed p-3">
					<p className="text-ink-subtle text-sm">Not on this resume</p>
					{unused.map((type) => (
						<div className="mt-2" key={type}>
							<h3 className="font-semibold text-sm">{SECTION_TITLES[type]}</h3>
							<AddRow
								catalogs={catalogs}
								draft={draft}
								onChange={onChange}
								type={type}
							/>
						</div>
					))}
				</div>
			)}
		</div>
	);
}
