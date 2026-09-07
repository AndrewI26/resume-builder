import { describe, expect, test } from "bun:test";
import { exportFilenames } from "./export-all";

/**
 * These cases mirror `scripts/export_resumes.py`. The two exports have to
 * produce the same folder, so the naming rules are checked against the same
 * expectations on both sides.
 */
describe("exportFilenames", () => {
	test("lowercases and hyphenates a title", () => {
		expect(exportFilenames(["Frontend Focused"])).toEqual([
			"frontend-focused.pdf",
		]);
	});

	test("replaces each punctuation character and trims the edges", () => {
		expect(exportFilenames(["  Senior (Backend) 2024!  "])).toEqual([
			"senior--backend--2024.pdf",
		]);
	});

	test("keeps letters the ASCII rules would have thrown away", () => {
		expect(exportFilenames(["Café"])).toEqual(["café.pdf"]);
	});

	test("falls back when a title has nothing usable in it", () => {
		expect(exportFilenames(["!!!"])).toEqual(["resume.pdf"]);
	});

	test("numbers collisions from two, leaving the first plain", () => {
		expect(exportFilenames(["Backend", "Backend", "Backend"])).toEqual([
			"backend.pdf",
			"backend-2.pdf",
			"backend-3.pdf",
		]);
	});

	test("titles that differ only in case still collide", () => {
		expect(exportFilenames(["Data Science", "data science"])).toEqual([
			"data-science.pdf",
			"data-science-2.pdf",
		]);
	});

	test("numbering is per stem, not per run", () => {
		expect(exportFilenames(["A", "B", "A"])).toEqual([
			"a.pdf",
			"b.pdf",
			"a-2.pdf",
		]);
	});
});
