import { describe, expect, test } from "bun:test";
import type { BulletPoint } from "../resume/types";
import { escapeLatex, escapeLatexUrl, renderBullet } from "./escape";

const bullet = (
	text: string,
	bolded: [number, number][] = [],
): BulletPoint => ({
	text,
	bolded,
});

describe("escapeLatex", () => {
	test.each([
		[
			"100% done",
			"100\\% done",
			"percent would comment out the rest of the line",
		],
		["Q&A", "Q\\&A", "ampersand is a table column separator"],
		["a_b", "a\\_b", "underscore is subscript"],
		["#1", "\\#1", "hash is a macro parameter"],
		["$5", "\\$5", "dollar opens math mode"],
		["{x}", "\\{x\\}", "braces group"],
		["a~b", "a\\textasciitilde{}b", "tilde is a non-breaking space"],
		["a^b", "a\\textasciicircum{}b", "caret is superscript"],
		["C:\\path", "C:\\textbackslash{}path", "backslash starts a macro"],
	])("escapes %p as %p (%s)", (input: string, expected: string) => {
		expect(escapeLatex(input)).toBe(expected);
	});

	test("escapes in a single pass, so a backslash's replacement is left alone", () => {
		// the naive order-dependent version turns this into
		// `\textbackslash\{\}`, escaping braces it just emitted itself
		expect(escapeLatex("\\")).toBe("\\textbackslash{}");
	});

	test("handles a string that is nothing but specials", () => {
		expect(escapeLatex("\\{}$&#_%~^")).toBe(
			"\\textbackslash{}\\{\\}\\$\\&\\#\\_\\%\\textasciitilde{}\\textasciicircum{}",
		);
	});

	test("leaves ordinary text untouched", () => {
		expect(escapeLatex("Senior Engineer, Platform")).toBe(
			"Senior Engineer, Platform",
		);
	});

	test("leaves accented characters untouched", () => {
		expect(escapeLatex("Zoë Ramírez")).toBe("Zoë Ramírez");
	});

	test("escapes an empty string to an empty string", () => {
		expect(escapeLatex("")).toBe("");
	});
});

describe("escapeLatexUrl", () => {
	test("leaves an ordinary URL alone", () => {
		expect(escapeLatexUrl("https://github.com/AndrewI26")).toBe(
			"https://github.com/AndrewI26",
		);
	});

	test.each([
		["https://x.com/~user", "https://x.com/%7Euser", "tilde"],
		["https://x.com/a#b", "https://x.com/a%23b", "fragment hash"],
		["https://x.com/a&b=1", "https://x.com/a%26b=1", "ampersand"],
		["https://x.com/a_b", "https://x.com/a%5Fb", "underscore"],
	])("percent-encodes %p as %p (%s)", (input: string, expected: string) => {
		expect(escapeLatexUrl(input)).toBe(expected);
	});

	test("preserves an existing percent-escape rather than double-encoding it", () => {
		expect(escapeLatexUrl("https://x.com/a%20b")).toBe("https://x.com/a%20b");
	});

	test("encodes a lone percent that is not a valid escape", () => {
		expect(escapeLatexUrl("https://x.com/100%")).toBe("https://x.com/100%25");
	});

	test("encodes a percent followed by too few hex digits", () => {
		expect(escapeLatexUrl("https://x.com/a%2")).toBe("https://x.com/a%252");
	});
});

describe("renderBullet", () => {
	test("renders plain text with no bolding", () => {
		expect(renderBullet(bullet("Shipped it"))).toBe("Shipped it");
	});

	test("bolds an inclusive range, covering its end character", () => {
		// [0, 6] over "Shipped it" is "Shipped", not "Shippe"
		expect(renderBullet(bullet("Shipped it", [[0, 6]]))).toBe(
			"\\textbf{Shipped} it",
		);
	});

	test("bolds a range at the end of the text", () => {
		expect(renderBullet(bullet("Shipped it", [[8, 9]]))).toBe(
			"Shipped \\textbf{it}",
		);
	});

	test("bolds a single character", () => {
		expect(renderBullet(bullet("abc", [[1, 1]]))).toBe("a\\textbf{b}c");
	});

	test("bolds several ranges", () => {
		expect(
			renderBullet(
				bullet("a b c", [
					[0, 0],
					[4, 4],
				]),
			),
		).toBe("\\textbf{a} b \\textbf{c}");
	});

	test("bolds the whole string", () => {
		expect(renderBullet(bullet("all", [[0, 2]]))).toBe("\\textbf{all}");
	});

	test("escapes inside a bolded range", () => {
		expect(renderBullet(bullet("100% up", [[0, 3]]))).toBe(
			"\\textbf{100\\%} up",
		);
	});

	test("escapes outside a bolded range", () => {
		expect(renderBullet(bullet("up 100%", [[0, 1]]))).toBe(
			"\\textbf{up} 100\\%",
		);
	});

	test("offsets index the raw text, not its escaped form", () => {
		// "&" escapes to two characters. Escaping first and then slicing would
		// bold "R\" here instead of "R&D".
		expect(renderBullet(bullet("R&D team", [[0, 2]]))).toBe(
			"\\textbf{R\\&D} team",
		);
	});

	test("sorts ranges given out of order", () => {
		expect(
			renderBullet(
				bullet("a b c", [
					[4, 4],
					[0, 0],
				]),
			),
		).toBe("\\textbf{a} b \\textbf{c}");
	});

	test("skips an overlapping range rather than nesting textbf", () => {
		expect(
			renderBullet(
				bullet("abcdef", [
					[0, 3],
					[2, 5],
				]),
			),
		).toBe("\\textbf{abcd}ef");
	});

	test("skips an inverted range", () => {
		expect(renderBullet(bullet("abc", [[2, 0]]))).toBe("abc");
	});

	test("handles empty text", () => {
		expect(renderBullet(bullet(""))).toBe("");
	});
});
