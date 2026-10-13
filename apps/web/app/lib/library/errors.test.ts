import { describe, expect, test } from "bun:test";
import { importProblems } from "./errors";

describe("importProblems", () => {
	test("turns a field error's location into a path into the file", () => {
		const problems = importProblems({
			detail: [
				{
					loc: ["body", "projects", 0, "name"],
					msg: "String should have at most 255 characters",
					type: "string_too_long",
				},
			],
		});

		expect(problems).toEqual([
			"projects[0].name: String should have at most 255 characters",
		]);
	});

	test("shows a problem with the whole file without a path", () => {
		const problems = importProblems({
			detail: [
				{
					loc: ["body"],
					msg: "Input should be a valid dictionary",
					type: "dict_type",
				},
			],
		});

		expect(problems).toEqual(["Input should be a valid dictionary"]);
	});

	test("passes a plain message through", () => {
		expect(importProblems({ detail: "Not authenticated" })).toEqual([
			"Not authenticated",
		]);
	});

	test("falls back when there is nothing to show", () => {
		expect(importProblems(undefined)).toEqual([
			"Could not import that file. Try again.",
		]);
	});
});
