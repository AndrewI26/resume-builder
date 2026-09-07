/**
 * The only thing the window learns about the machine it is running on.
 *
 * The renderer is the same bundle a browser loads and is treated with the same
 * suspicion: context isolation is on, Node is off, and what crosses this
 * boundary is two strings and two functions. The strings cannot be baked into
 * the bundle because neither exists until the app launches — the port is
 * chosen at runtime and the token is generated per run.
 *
 * The functions are the app's only way onto the filesystem, and they are
 * deliberately narrow: ask a person for a folder, clear the PDFs out of one
 * they have agreed to empty, and put a named PDF in it. None of them decides
 * anything — the main process checks every path it is given, because a preload
 * script runs alongside the page and is no safer than the page is. In
 * particular, nothing here is what makes the deletion safe: the warning is the
 * app's, and the refusal to touch an unchosen folder is the main process's.
 *
 * `packages/ui/app/platform/host.ts` is the other side of this.
 */

import { contextBridge, ipcRenderer } from "electron";
import {
	CHOOSE_DIRECTORY_CHANNEL,
	type ChosenDirectory,
	CLEAR_CHANNEL,
	WRITE_CHANNEL,
} from "../shared/export-channels";

contextBridge.exposeInMainWorld("resumeBuilderHost", {
	apiBaseUrl: process.env.RESUME_BUILDER_API_URL,
	apiToken: process.env.RESUME_BUILDER_API_TOKEN,

	/**
	 * Opens the system folder picker. Null when it was dismissed.
	 *
	 * Comes back with a count of the PDFs already in the folder, which is what
	 * the app needs to warn about before it clears them.
	 */
	chooseExportDirectory: (): Promise<ChosenDirectory | null> =>
		ipcRenderer.invoke(CHOOSE_DIRECTORY_CHANNEL),

	/** Deletes the PDFs in a chosen folder. Returns how many went. */
	clearExportedPdfs: (directory: string): Promise<number> =>
		ipcRenderer.invoke(CLEAR_CHANNEL, directory),

	/** Writes one PDF into a folder the picker returned earlier. */
	writeExportedPdf: (
		directory: string,
		filename: string,
		contents: Uint8Array,
	): Promise<void> =>
		ipcRenderer.invoke(WRITE_CHANNEL, directory, filename, contents),
});
