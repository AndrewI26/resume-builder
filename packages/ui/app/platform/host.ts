/**
 * Where the app is running, and what follows from it.
 *
 * The same screens run in a browser tab and inside the desktop shell. In the
 * browser the API is a known address baked in at build time. On the desktop it
 * is a server the shell started a moment ago on a port it picked at random, so
 * the address cannot be known until the window opens — and every request has
 * to carry the secret proving it comes from this app rather than from
 * something else running on the same machine.
 *
 * Both facts arrive from the shell through its preload bridge, along with the
 * only three things the app can do to the filesystem: ask for a folder, empty
 * it of PDFs, and put a PDF in one that was asked for. A browser tab has none
 * of them, which is why exporting a whole library to a folder is a
 * desktop-only offer.
 *
 * Everything reads all of this from here rather than reaching for the global,
 * so one place knows the difference exists.
 */

/** A folder the person chose, and what an export there would destroy. */
export type ChosenDirectory = { path: string; existingPdfs: number };

/** What the desktop shell puts on the window. Absent in a browser. */
export type DesktopHost = {
	/** The sidecar's address, chosen when the app launched. */
	apiBaseUrl: string;
	/** Proves a request came from this window. */
	apiToken: string;
	/**
	 * Opens the system folder picker; null if it was dismissed.
	 *
	 * Choosing is what grants the two calls below — the shell will not touch a
	 * folder that did not come back from here. `existingPdfs` counts what an
	 * export there would destroy, so the warning can name a number.
	 */
	chooseExportDirectory: () => Promise<ChosenDirectory | null>;
	/**
	 * Deletes every PDF sitting directly in the folder. Returns how many went.
	 *
	 * Destructive and not undoable, including for files this app never wrote —
	 * never call it without asking first.
	 */
	clearExportedPdfs: (directory: string) => Promise<number>;
	/** Writes one PDF into a folder `chooseExportDirectory` returned. */
	writeExportedPdf: (
		directory: string,
		filename: string,
		contents: Uint8Array,
	) => Promise<void>;
};

declare global {
	interface Window {
		resumeBuilderHost?: DesktopHost;
	}
}

const host: DesktopHost | undefined =
	typeof window === "undefined" ? undefined : window.resumeBuilderHost;

/** Running inside the desktop shell rather than a browser tab. */
export const isDesktop = host !== undefined;

export const apiBaseUrl: string =
	host?.apiBaseUrl ??
	import.meta.env.VITE_API_BASE_URL ??
	"http://localhost:8000";

/**
 * The shell's filesystem bridge, or null in a browser.
 *
 * Returned whole rather than as two exported functions so callers cannot end
 * up holding one without the other, and so the null check that decides whether
 * to offer the feature is the same one that narrows the type.
 */
export function fileExporter(): Pick<
	DesktopHost,
	"chooseExportDirectory" | "clearExportedPdfs" | "writeExportedPdf"
> | null {
	// A desktop build older than this bridge is still a desktop build, so all
	// three are checked rather than assumed from `isDesktop`. All or nothing on
	// purpose: an export that could write but not clear would leave a folder
	// holding a mix of this run and the last one.
	if (
		host === undefined ||
		typeof host.chooseExportDirectory !== "function" ||
		typeof host.clearExportedPdfs !== "function" ||
		typeof host.writeExportedPdf !== "function"
	) {
		return null;
	}

	return {
		chooseExportDirectory: host.chooseExportDirectory,
		clearExportedPdfs: host.clearExportedPdfs,
		writeExportedPdf: host.writeExportedPdf,
	};
}

/**
 * Headers every request to the API must carry.
 *
 * Empty in the browser, where the session is a cookie and the server is the
 * one this bundle was built against.
 */
export function apiHeaders(): Record<string, string> {
	return host ? { "x-sidecar-token": host.apiToken } : {};
}
