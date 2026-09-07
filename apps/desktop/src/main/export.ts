/**
 * Writing exported resumes to a folder the person picked.
 *
 * The renderer does the compiling — it already knows how to ask the sidecar
 * for one resume's PDF, and doing all of them is that request in a loop. What
 * it cannot do is touch the disk, which is the whole point of the sandbox it
 * runs in. So the two halves meet here: the window says "put these bytes in
 * that folder under that name", and this decides whether it may.
 *
 * The rule is that a folder is writable only because a person chose it in the
 * system dialog during this run. Nothing else grants it — not a path typed
 * into the app, not one remembered from last time. A renderer that has been
 * talked into something by a malicious resume can therefore only touch PDFs
 * inside a directory its user just pointed at.
 *
 * That matters more here than it would for writing alone, because an export
 * clears the folder's existing PDFs first — the same thing the command-line
 * script does, so that what lands there is the export and nothing else. The
 * warning in front of it is the renderer's job; this end only refuses folders
 * nobody chose, and never touches anything that is not a PDF sitting directly
 * in one.
 *
 * The checks themselves are in `shared/export-paths`, where they can be tested.
 */

import { BrowserWindow, dialog, ipcMain } from "electron";
import { readdir, unlink, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
	CHOOSE_DIRECTORY_CHANNEL,
	type ChosenDirectory,
	CLEAR_CHANNEL,
	WRITE_CHANNEL,
} from "../shared/export-channels";
import { containedPath, exportTarget, isPdfName } from "../shared/export-paths";

/**
 * Folders a person has chosen in this run, resolved.
 *
 * Kept in the main process rather than handed to the renderer as a capability,
 * because a value the renderer holds is a value the renderer can be tricked
 * into replaying. It is never cleared: the grant lasts the session, which is
 * how long the export flow that opened it can plausibly still be running.
 */
const grantedDirectories = new Set<string>();

/**
 * Ask for a folder, and remember that this one was allowed.
 *
 * Returns null when the dialog was dismissed, which is an ordinary outcome and
 * not an error — the person changed their mind about exporting.
 */
async function chooseDirectory(
	window: BrowserWindow | null,
): Promise<ChosenDirectory | null> {
	const options: Electron.OpenDialogOptions = {
		title: "Choose a folder for your resumes",
		buttonLabel: "Export here",
		// createDirectory earns its place: "put these in a new Applications
		// folder" is the obvious thing to want here, and without it that means
		// leaving the app to make one first.
		properties: ["openDirectory", "createDirectory"],
	};

	const result = await (window === null
		? dialog.showOpenDialog(options)
		: dialog.showOpenDialog(window, options));

	const [chosen] = result.filePaths;
	if (result.canceled || chosen === undefined) {
		return null;
	}

	const directory = resolve(chosen);
	grantedDirectories.add(directory);

	// Counted here rather than left for a second round trip, because the
	// warning the renderer is about to show has to say how many files are
	// actually at stake — "some PDFs" is not a thing to ask someone to agree to.
	return { path: directory, existingPdfs: (await pdfsIn(directory)).length };
}

/**
 * The PDFs an export into this folder would delete.
 *
 * Only files sitting directly in the folder, and only PDFs: the target may be
 * somewhere the person keeps other things, and nothing here has any business
 * removing those. Sub-folders are left alone entirely.
 */
async function pdfsIn(directory: string): Promise<string[]> {
	const root = resolve(directory);

	if (!grantedDirectories.has(root)) {
		throw new Error("that folder was not chosen for an export");
	}

	const entries = await readdir(root, { withFileTypes: true }).catch(() => []);

	return entries
		.filter((entry) => entry.isFile() && isPdfName(entry.name))
		.map((entry) => entry.name)
		.sort();
}

/**
 * Delete those PDFs. Returns how many went.
 *
 * Only ever called once the person has read the count and agreed to it. A file
 * that vanished between the count and here is not an error — something else
 * removed it, and the folder is in the state we were asking for either way.
 */
async function clear(directory: string): Promise<number> {
	const root = resolve(directory);
	let deleted = 0;

	for (const name of await pdfsIn(root)) {
		const path = containedPath(root, name);
		if (path === null) {
			continue;
		}

		try {
			await unlink(path);
			deleted += 1;
		} catch (error) {
			if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
				throw error;
			}
		}
	}

	return deleted;
}

/**
 * Write one PDF into a granted folder.
 *
 * By the time this runs the folder has already been cleared, so there is
 * normally nothing to replace; it still overwrites rather than refusing, so a
 * name colliding with something created in the meantime does not fail the run.
 */
async function write(
	directory: string,
	filename: string,
	contents: Uint8Array,
): Promise<void> {
	const target = exportTarget(directory, filename, grantedDirectories);

	if ("error" in target) {
		throw new Error(target.error);
	}

	await writeFile(target.path, contents);
}

/** Wire both channels up. Called once, before any window exists. */
export function registerExportHandlers(): void {
	ipcMain.handle(CHOOSE_DIRECTORY_CHANNEL, (event) =>
		chooseDirectory(BrowserWindow.fromWebContents(event.sender)),
	);

	ipcMain.handle(CLEAR_CHANNEL, (_event, directory: string) =>
		clear(directory),
	);

	ipcMain.handle(
		WRITE_CHANNEL,
		(_event, directory: string, filename: string, contents: Uint8Array) =>
			write(directory, filename, contents),
	);
}
