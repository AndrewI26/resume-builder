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

	test("splits the cross reference check into one line per problem", () => {
		const problems = importProblems({
			detail: [
				{
					loc: ["body"],
					msg: "Value error, resumes[0].personal_info: no personal_info entry has key 'x'; resumes[0].sections.project[0]: no projects entry has key 'y'",
					type: "value_error",
				},
			],
		});

		expect(problems).toEqual([
			"resumes[0].personal_info: no personal_info entry has key 'x'",
			"resumes[0].sections.project[0]: no projects entry has key 'y'",
		]);
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
