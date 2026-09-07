import { describe, expect, test } from "bun:test";
import { resolve } from "node:path";
import {
	containedPath,
	exportTarget,
	isPdfName,
	isSafeFilename,
} from "./export-paths";

const chosen = resolve("/tmp/resumes");
const granted = new Set([chosen]);

const error = (directory: string, filename: string): string => {
	const result = exportTarget(directory, filename, granted);
	return "error" in result ? result.error : "";
};

describe("isSafeFilename", () => {
	test("accepts a name the exporter produces", () => {
		expect(isSafeFilename("frontend-focused.pdf")).toBe(true);
	});

	test("accepts letters outside ASCII", () => {
		expect(isSafeFilename("café.pdf")).toBe(true);
	});

	test.each([
		["../escape.pdf", "a relative traversal"],
		["/etc/passwd.pdf", "an absolute path"],
		["nested/file.pdf", "a subdirectory"],
		["resume.pdf.exe", "a second extension"],
		["resume.tex", "a non-PDF"],
		[".hidden.pdf", "a leading dot"],
		["-resume.pdf", "a leading hyphen"],
		["", "an empty name"],
	])("rejects %p — %s", (filename) => {
		expect(isSafeFilename(filename)).toBe(false);
	});
});

describe("exportTarget", () => {
	test("resolves a name inside the folder that was chosen", () => {
		expect(exportTarget(chosen, "backend.pdf", granted)).toEqual({
			path: resolve(chosen, "backend.pdf"),
		});
	});

	test("refuses a folder nobody chose, even a plausible one", () => {
		expect(error(resolve("/tmp/elsewhere"), "backend.pdf")).toMatch(
			/not chosen/,
		);
	});

	// The folder check comes first on purpose: an unchosen folder is refused
	// whatever the filename, so a caller cannot learn which names are legal by
	// probing somewhere it has no business writing.
	test("refuses an unchosen folder before it looks at the name", () => {
		expect(error(resolve("/tmp/elsewhere"), "../../etc/passwd")).toMatch(
			/not chosen/,
		);
	});

	test("refuses to climb out of the folder that was chosen", () => {
		expect(error(chosen, "../escape.pdf")).toMatch(/refusing to write/);
	});

	test("treats an unresolved path as the folder it resolves to", () => {
		expect(
			exportTarget(`${chosen}/../resumes`, "backend.pdf", granted),
		).toEqual({ path: resolve(chosen, "backend.pdf") });
	});
});

/**
 * What an export is willing to delete. Mirrors `existing_pdfs` in
 * `scripts/export_resumes.py`, which judges by suffix and nothing else.
 */
describe("isPdfName", () => {
	test.each([
		["backend.pdf", "an exported name"],
		["Some Old Resume.pdf", "a name this app would never write"],
		["scan.PDF", "an uppercase extension"],
		[".hidden.pdf", "a hidden file"],
	])("deletes %p — %s", (name) => {
		expect(isPdfName(name)).toBe(true);
	});

	test.each([
		["notes.txt", "another file type"],
		["resume.pdf.bak", "a PDF that was renamed away"],
		[".pdf", "a bare extension, which Python reads as a stem"],
		["nested/backend.pdf", "something in a sub-folder"],
		["", "an empty name"],
	])("spares %p — %s", (name) => {
		expect(isPdfName(name)).toBe(false);
	});
});

describe("containedPath", () => {
	test("resolves an entry sitting in the folder", () => {
		expect(containedPath(chosen, "backend.pdf")).toBe(
			resolve(chosen, "backend.pdf"),
		);
	});

	test("refuses an entry that climbs out of it", () => {
		expect(containedPath(chosen, "../backend.pdf")).toBeNull();
	});

	test("refuses an absolute path wearing an entry's clothes", () => {
		expect(containedPath(chosen, "/etc/backend.pdf")).toBeNull();
	});
});
