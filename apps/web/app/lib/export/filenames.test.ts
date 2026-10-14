import { describe, expect, test } from "bun:test";
import { filenames, isPdfName, slug } from "./filenames";

describe("slug", () => {
	test("turns each character that isn't a letter or digit into a hyphen", () => {
		expect(slug("C++ / Rust")).toBe("c-----rust");
		expect(slug("Café Résumé")).toBe("café-résumé");
	});

	test("falls back when nothing is left", () => {
		expect(slug("!!!")).toBe("resume");
	});
});

describe("filenames", () => {
	test("numbers repeated names from 2", () => {
		expect(filenames(["Backend", "backend", "Frontend", "Backend"])).toEqual([
			"backend.pdf",
			"backend-2.pdf",
			"frontend.pdf",
			"backend-3.pdf",
		]);
	});
});

describe("isPdfName", () => {
	test("accepts plain PDF names only", () => {
		expect(isPdfName("a.pdf")).toBe(true);
		expect(isPdfName("A.PDF")).toBe(true);
		expect(isPdfName(".pdf")).toBe(false);
		expect(isPdfName("notes.txt")).toBe(false);
		expect(isPdfName("../a.pdf")).toBe(false);
	});
});
