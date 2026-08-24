import { describe, expect, test } from "bun:test";
import { typeset } from "./typography";

describe("typeset", () => {
	test("turns a double hyphen into an en dash", () => {
		expect(typeset("May 2025 -- August 2025")).toBe("May 2025 – August 2025");
	});

	test("turns a triple hyphen into an em dash", () => {
		expect(typeset("a---b")).toBe("a—b");
	});

	test("leaves a single hyphen alone", () => {
		expect(typeset("Full-stack Developer")).toBe("Full-stack Developer");
	});

	test("matches TeX on a run of four hyphens", () => {
		// TeX's ligatures are greedy and chain: `--` forms an en dash, the en
		// dash plus a third hyphen forms an em dash, and the fourth has nothing
		// left to combine with, so it stays a hyphen.
		expect(typeset("a----b")).toBe("a—-b");
	});

	test("converts several dashes in one string", () => {
		expect(typeset("a -- b -- c")).toBe("a – b – c");
	});

	test("leaves text with no dashes untouched", () => {
		expect(typeset("Software Engineer")).toBe("Software Engineer");
	});
});
