import { apiBaseUrl } from "~/platform/host";

const EXPORT_FILENAME = "resume-builder-library.json";

/**
 * Download the signed in user's whole library in the import format.
 *
 * Outside the typed client because the result is saved as a file rather than
 * read: the browser only offers a download for an object URL on an anchor.
 */
export async function downloadLibraryExport(): Promise<void> {
	const response = await fetch(`${apiBaseUrl}/library/export`, {
		credentials: "include",
	});
	if (!response.ok) {
		throw new Error("Could not export your library. Try again.");
	}

	const url = URL.createObjectURL(await response.blob());
	const anchor = document.createElement("a");
	anchor.href = url;
	anchor.download = EXPORT_FILENAME;
	anchor.click();
	URL.revokeObjectURL(url);
}
