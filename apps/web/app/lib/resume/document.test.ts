import { describe, expect, test } from "bun:test";
import {
	attach,
	buildDocument,
	type Catalogs,
	detach,
	isDirty,
	moveItem,
	moveWithinType,
	type ResumeDraft,
	refsOfType,
	setTypeOrder,
	swap,
} from "./document";
import type { Education, Skill } from "./types";

const education = (id: string, name: string): Education => ({
	id,
	name,
	subheading: "BSc",
	duration: "2020 - 2024",
	location: "Boston, MA",
});

const skill = (id: string, name: string): Skill => ({
	id,
	name,
	items: ["a", "b"],
	position: 0,
});

const catalogs: Catalogs = {
	education: [education("e1", "First"), education("e2", "Second")],
	experience: [],
	project: [],
	skill: [skill("s1", "Languages"), skill("s2", "Tools")],
};

const draft = (overrides: Partial<ResumeDraft> = {}): ResumeDraft => ({
	order: ["education", "skill"],
	sections: [
		{ section_type: "education", section_id: "e1" },
		{ section_type: "skill", section_id: "s1" },
		{ section_type: "education", section_id: "e2" },
	],
	...overrides,
});

function build(current: ResumeDraft) {
	return buildDocument({
		id: "r1",
		title: "Untitled",
		template: "jakes",
		fullName: "Ada Lovelace",
		personalInfo: null,
		draft: current,
		catalogs,
	});
}

describe("buildDocument", () => {
	test("orders blocks by the draft's order, not the membership list", () => {
		const document = build(draft({ order: ["skill", "education"] }));

		expect(document.sections.map((block) => block.type)).toEqual([
			"skill",
			"education",
		]);
	});

	test("keeps each type's items in the order the draft lists them", () => {
		const document = build(draft());
		const block = document.sections.find((item) => item.type === "education");

		expect(block?.items.map((item) => item.id)).toEqual(["e1", "e2"]);
	});

	test("drops a block whose type is attached but not ordered", () => {
		const document = build(draft({ order: ["education"] }));

		expect(document.sections.map((block) => block.type)).toEqual(["education"]);
	});

	test("drops a ref whose row no longer exists", () => {
		const document = build(
			draft({
				sections: [
					{ section_type: "education", section_id: "e1" },
					{ section_type: "education", section_id: "gone" },
				],
			}),
		);
		const block = document.sections.find((item) => item.type === "education");

		expect(block?.items.map((item) => item.id)).toEqual(["e1"]);
	});

	test("drops a heading with nothing under it", () => {
		const document = build(draft({ sections: [] }));

		expect(document.sections).toEqual([]);
	});
});

describe("moveItem", () => {
	test("moves an item down", () => {
		expect(moveItem(["a", "b", "c"], 0, 2)).toEqual(["b", "c", "a"]);
	});

	test("moves an item up", () => {
		expect(moveItem(["a", "b", "c"], 2, 0)).toEqual(["c", "a", "b"]);
	});

	test("refuses to move past either end", () => {
		expect(moveItem(["a", "b"], 0, -1)).toEqual(["a", "b"]);
		expect(moveItem(["a", "b"], 1, 2)).toEqual(["a", "b"]);
	});
});

describe("moveWithinType", () => {
	test("reorders one type without disturbing the others", () => {
		const next = moveWithinType(draft(), "education", 0, 1);

		expect(refsOfType(next, "education").map((ref) => ref.section_id)).toEqual([
			"e2",
			"e1",
		]);
		expect(refsOfType(next, "skill").map((ref) => ref.section_id)).toEqual([
			"s1",
		]);
	});

	test("the reordered document renders in the new order", () => {
		const next = moveWithinType(draft(), "education", 0, 1);
		const block = build(next).sections.find(
			(item) => item.type === "education",
		);

		expect(block?.items.map((item) => item.name)).toEqual(["Second", "First"]);
	});
});

describe("setTypeOrder", () => {
	test("takes the reordered list as given", () => {
		const current = refsOfType(draft(), "education");
		const next = setTypeOrder(draft(), "education", [current[1], current[0]]);

		expect(refsOfType(next, "education").map((ref) => ref.section_id)).toEqual([
			"e2",
			"e1",
		]);
	});

	test("leaves the other types where they were", () => {
		const current = refsOfType(draft(), "education");
		const next = setTypeOrder(draft(), "education", [current[1], current[0]]);

		expect(next.sections[1]).toEqual({
			section_type: "skill",
			section_id: "s1",
		});
	});

	/**
	 * The drag hook hands back a whole reordered array. Deriving a (from, to)
	 * pair from it by diffing looked equivalent and was not: for an upward move
	 * the first differing index is not the row that moved, and re-applying the
	 * derived pair produced a different list than the one dragged.
	 */
	test("round-trips a drag of the last row to the top", () => {
		const start = draft({
			order: ["education"],
			sections: [
				{ section_type: "education", section_id: "e1" },
				{ section_type: "education", section_id: "e2" },
				{ section_type: "education", section_id: "e3" },
			],
		});
		const current = refsOfType(start, "education");
		const dragged = moveItem(current, 2, 0);

		const next = setTypeOrder(start, "education", dragged);

		expect(refsOfType(next, "education").map((ref) => ref.section_id)).toEqual([
			"e3",
			"e1",
			"e2",
		]);
	});
});

describe("attach", () => {
	test("appends after the others of its type", () => {
		const next = attach(draft({ sections: [] }), {
			section_type: "education",
			section_id: "e2",
		});

		expect(next.sections).toEqual([
			{ section_type: "education", section_id: "e2" },
		]);
	});

	test("ignores a row that is already attached", () => {
		const before = draft();
		const next = attach(before, {
			section_type: "education",
			section_id: "e1",
		});

		expect(next).toBe(before);
	});

	test("gives a newly used type a heading at the end", () => {
		const next = attach(draft({ order: ["education"] }), {
			section_type: "skill",
			section_id: "s2",
		});

		expect(next.order).toEqual(["education", "skill"]);
	});
});

describe("detach", () => {
	test("removes just that row", () => {
		const next = detach(draft(), {
			section_type: "education",
			section_id: "e1",
		});

		expect(refsOfType(next, "education").map((ref) => ref.section_id)).toEqual([
			"e2",
		]);
	});

	test("leaves the heading in place for whatever else is under it", () => {
		const next = detach(draft(), {
			section_type: "education",
			section_id: "e1",
		});

		expect(next.order).toEqual(["education", "skill"]);
	});
});

describe("swap", () => {
	test("replaces the row but keeps its position", () => {
		const next = swap(
			draft(),
			{ section_type: "education", section_id: "e1" },
			"e2",
		);

		expect(next.sections[0]).toEqual({
			section_type: "education",
			section_id: "e2",
		});
	});
});

describe("isDirty", () => {
	test("is false for an untouched draft", () => {
		expect(isDirty(draft(), draft())).toBe(false);
	});

	test("notices a reordered heading", () => {
		expect(isDirty(draft({ order: ["skill", "education"] }), draft())).toBe(
			true,
		);
	});

	test("notices a detached row", () => {
		const next = detach(draft(), {
			section_type: "education",
			section_id: "e1",
		});

		expect(isDirty(next, draft())).toBe(true);
	});

	test("notices a reordered row", () => {
		expect(isDirty(moveWithinType(draft(), "education", 0, 1), draft())).toBe(
			true,
		);
	});
});
