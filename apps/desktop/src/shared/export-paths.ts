/**
 * Deciding where an exported PDF is allowed to land.
 *
 * Kept apart from the IPC handlers so it can be tested without an Electron
 * runtime — this is the check standing between a compromised renderer and the
 * filesystem, and a check that is never exercised is a check nobody should
 * trust. Nothing here touches the disk or the dialog; it answers a question
 * about strings and lets the caller act on it.
 *
 * Imports `node:path` and so must never be pulled into the preload bundle;
 * the channel names live in their own file for that reason.
 */

import { basename, dirname, join, resolve } from "node:path";

/**
 * A name we are willing to create: one plain PDF file, no path in it.
 *
 * Letters and digits are the Unicode ones rather than ASCII, because the names
 * are built from resume titles and "Café" is a title someone will have. What
 * matters is that separators, dots and device names cannot appear — not that
 * the alphabet is English.
 */
const SAFE_FILENAME = /^[\p{L}\p{N}][\p{L}\p{N}-]*\.pdf$/u;

/**
 * Refuse anything that is not a bare filename.
 *
 * `basename` alone is not enough — it would quietly turn "../../secrets.pdf"
 * into "secrets.pdf" and write it, which is a different file than the one the
 * caller named. Anything that does not survive the round trip unchanged is a
 * traversal attempt, and the answer to those is no rather than a guess.
 */
export function isSafeFilename(filename: string): boolean {
	return (
		basename(filename) === filename &&
		SAFE_FILENAME.test(filename.toLowerCase())
	);
}

/**
 * Whether a directory entry is one of the PDFs an export replaces.
 *
 * Mirrors the script's rule exactly: a name ending in `.pdf`, with something
 * in front of it. The length check is what excludes a file called plainly
 * ".pdf" — Python reads that as a stem with no extension, so the script leaves
 * it alone and so does this. Callers must still confirm the entry is a file
 * and sits directly in the folder; this only judges the name.
 */
export function isPdfName(name: string): boolean {
	return (
		name.length > ".pdf".length &&
		basename(name) === name &&
		name.toLowerCase().endsWith(".pdf")
	);
}

/**
 * The absolute path of an entry inside a folder, or null if it escapes.
 *
 * Used for names that came back from reading the folder rather than from the
 * renderer, so this is a sanity check rather than a boundary — but a symlinked
 * or oddly-named entry resolving somewhere else is exactly the case where
 * deleting without looking would be unforgivable.
 */
export function containedPath(root: string, name: string): string | null {
	const path = resolve(join(root, name));
	return dirname(path) === resolve(root) ? path : null;
}

/**
 * The absolute path to write, or an explanation of why there isn't one.
 *
 * `granted` is the set of folders a person chose in the system dialog during
 * this run, already resolved. Membership is the only thing that authorises a
 * write: a path the renderer invented, however well-formed, is not in it.
 */
export function exportTarget(
	directory: string,
	filename: string,
	granted: ReadonlySet<string>,
): { path: string } | { error: string } {
	const root = resolve(directory);

	if (!granted.has(root)) {
		return { error: "that folder was not chosen for an export" };
	}

	if (!isSafeFilename(filename)) {
		return { error: `refusing to write ${filename}` };
	}

	const path = resolve(join(root, filename));

	// Belt and braces over the filename check: whatever the two of them
	// concluded, the file has to land directly in the folder that was granted.
	if (dirname(path) !== root) {
		return { error: `refusing to write outside ${root}` };
	}

	return { path };
}
