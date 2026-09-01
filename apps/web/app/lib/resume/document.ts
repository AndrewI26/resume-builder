/**
 * Assembling a `ResumeDocument` on the client.
 *
 * `GET /resumes/{id}/document` builds this server-side, but the editor needs
 * the same structure to change as someone drags a row — before anything is
 * saved. So the preview is fed from here instead: the catalogs supply the
 * content, the draft supplies the order and the membership, and every edit is
 * a new document without a round trip.
 *
 * The server remains the authority. Saving writes the draft back, and the PDF
 * is built from the rows, not from this.
 */

import type {
	Education,
	Experience,
	PersonalInfo,
	Project,
	ResumeDocument,
	SectionBlock,
	SectionType,
	Skill,
} from "./types";

/** One attached section: which table it lives in, and which row. */
export interface SectionRef {
	section_type: SectionType;
	section_id: string;
}

/** Everything the user could attach, by type. */
export interface Catalogs {
	education: Education[];
	experience: Experience[];
	project: Project[];
	skill: Skill[];
}

export const EMPTY_CATALOGS: Catalogs = {
	education: [],
	experience: [],
	project: [],
	skill: [],
};

/**
 * The editable state of a resume.
 *
 * `order` is which headings appear and in what order; `sections` is which rows
 * are attached and — within each type — in what order. The two are separate in
 * the API for a reason: a type can be attached but not ordered, which is how a
 * section is hidden without being detached.
 */
export interface ResumeDraft {
	order: SectionType[];
	sections: SectionRef[];
}

export const SECTION_TYPES: SectionType[] = [
	"education",
	"experience",
	"project",
	"skill",
];

export const SECTION_TITLES: Record<SectionType, string> = {
	education: "Education",
	experience: "Experience",
	project: "Projects",
	skill: "Skills",
};

/** A one-line description of a row, for the editor's lists and pickers. */
export function describe(
	type: SectionType,
	row: Education | Experience | Project | Skill,
): string {
	switch (type) {
		case "education":
			return (row as Education).name;
		case "experience": {
			const experience = row as Experience;
			return `${experience.position} at ${experience.company}`;
		}
		case "project":
			return (row as Project).name;
		case "skill":
			return (row as Skill).name;
	}
}

/** Look one row up in the catalogs, or `undefined` if it is gone. */
export function findRow(
	catalogs: Catalogs,
	ref: SectionRef,
): Education | Experience | Project | Skill | undefined {
	return catalogs[ref.section_type].find(
		(row: { id: string }) => row.id === ref.section_id,
	);
}

/** The attached refs of one type, in the order the draft lists them. */
export function refsOfType(
	draft: ResumeDraft,
	type: SectionType,
): SectionRef[] {
	return draft.sections.filter((ref) => ref.section_type === type);
}

function blockFor(
	type: SectionType,
	draft: ResumeDraft,
	catalogs: Catalogs,
): SectionBlock {
	const ids = refsOfType(draft, type).map((ref) => ref.section_id);
	const byId = new Map(catalogs[type].map((row) => [row.id, row]));
	// a row deleted from under the resume leaves a stale ref behind; drop it
	// rather than rendering a hole
	const items = ids
		.map((id) => byId.get(id))
		.filter((row): row is NonNullable<typeof row> => row !== undefined);

	// the cast is what the discriminated union costs: `type` is only known to
	// be a SectionType here, so TypeScript cannot pair it with its own items
	return { type, items } as SectionBlock;
}

/** Build the document the preview renders. */
export function buildDocument({
	id,
	title,
	template,
	fullName,
	personalInfo,
	draft,
	catalogs,
}: {
	id: string;
	title: string;
	template: string;
	fullName: string;
	personalInfo: PersonalInfo | null;
	draft: ResumeDraft;
	catalogs: Catalogs;
}): ResumeDocument {
	const sections = draft.order
		.map((type) => blockFor(type, draft, catalogs))
		// an empty block would render as a bare heading
		.filter((block) => block.items.length > 0);

	return {
		id,
		title,
		template,
		full_name: fullName,
		personal_info: personalInfo,
		sections,
	};
}

/** Move the item at `from` so it lands at `to`. */
export function moveItem<T>(items: T[], from: number, to: number): T[] {
	if (to < 0 || to >= items.length || from === to) {
		return items;
	}

	const next = [...items];
	const [moved] = next.splice(from, 1);
	next.splice(to, 0, moved);
	return next;
}

/**
 * Give one type's refs a new order, leaving every other type's run untouched.
 *
 * `sections` interleaves the types in one flat list, and only the order
 * *within* a type is meaningful to the API, so this refills the positions that
 * belong to `type` and puts the rest back where they were.
 */
export function setTypeOrder(
	draft: ResumeDraft,
	type: SectionType,
	ordered: SectionRef[],
): ResumeDraft {
	let next = 0;
	return {
		...draft,
		sections: draft.sections.map((ref) =>
			ref.section_type === type ? ordered[next++] : ref,
		),
	};
}

/** Move one of a type's refs from one index to another. */
export function moveWithinType(
	draft: ResumeDraft,
	type: SectionType,
	from: number,
	to: number,
): ResumeDraft {
	const current = refsOfType(draft, type);
	const moved = moveItem(current, from, to);

	return moved === current ? draft : setTypeOrder(draft, type, moved);
}

/** Attach a row, appending it after the others of its type. */
export function attach(draft: ResumeDraft, ref: SectionRef): ResumeDraft {
	const alreadyThere = draft.sections.some(
		(existing) =>
			existing.section_type === ref.section_type &&
			existing.section_id === ref.section_id,
	);
	if (alreadyThere) {
		return draft;
	}

	return {
		// a type attached but never ordered would render nowhere, so give it a
		// heading at the end rather than silently swallowing the row
		order: draft.order.includes(ref.section_type)
			? draft.order
			: [...draft.order, ref.section_type],
		sections: [...draft.sections, ref],
	};
}

/** Detach a row, leaving its heading in the order for whatever else is there. */
export function detach(draft: ResumeDraft, ref: SectionRef): ResumeDraft {
	return {
		...draft,
		sections: draft.sections.filter(
			(existing) =>
				existing.section_type !== ref.section_type ||
				existing.section_id !== ref.section_id,
		),
	};
}

/** Swap one attached row for another of the same type, keeping its place. */
export function swap(
	draft: ResumeDraft,
	ref: SectionRef,
	nextId: string,
): ResumeDraft {
	return {
		...draft,
		sections: draft.sections.map((existing) =>
			existing.section_type === ref.section_type &&
			existing.section_id === ref.section_id
				? { ...existing, section_id: nextId }
				: existing,
		),
	};
}

/** True when the draft differs from what was loaded. */
export function isDirty(draft: ResumeDraft, saved: ResumeDraft): boolean {
	return (
		draft.order.join() !== saved.order.join() ||
		draft.sections
			.map((ref) => `${ref.section_type}:${ref.section_id}`)
			.join() !==
			saved.sections
				.map((ref) => `${ref.section_type}:${ref.section_id}`)
				.join()
	);
}
