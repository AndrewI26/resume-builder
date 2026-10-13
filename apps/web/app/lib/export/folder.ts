import { isPdfName } from "./filenames";

/**
 * Writing into a folder on the person's computer, through the File System
 * Access API. Only Chromium browsers on desktop have `showDirectoryPicker`;
 * Firefox and Safari don't, so callers check `canExportToFolder` and offer a
 * ZIP instead. TypeScript's DOM types leave the picker and directory
 * iteration out, hence the small declarations here.
 */

type DirectoryPickerOptions = {
	id?: string;
	mode?: "read" | "readwrite";
	startIn?: string;
};

type IterableDirectoryHandle = FileSystemDirectoryHandle & {
	values(): AsyncIterable<FileSystemHandle>;
};

type WindowWithPicker = Window & {
	showDirectoryPicker?: (
		options?: DirectoryPickerOptions,
	) => Promise<FileSystemDirectoryHandle>;
};

export function canExportToFolder(): boolean {
	return (
		typeof window !== "undefined" &&
		typeof (window as WindowWithPicker).showDirectoryPicker === "function"
	);
}

/** Ask for a folder, or return null if the person backed out. */
export async function pickFolder(): Promise<FileSystemDirectoryHandle | null> {
	const picker = (window as WindowWithPicker).showDirectoryPicker;
	if (picker === undefined) {
		throw new Error("This browser can't save into a folder.");
	}

	try {
		// the id makes the picker open where it was last used
		return await picker({ id: "resume-pdfs", mode: "readwrite" });
	} catch (error) {
		if (error instanceof DOMException && error.name === "AbortError") {
			return null;
		}
		throw error;
	}
}

/**
 * The PDFs directly in the folder. Only PDFs, and nothing in subfolders: the
 * folder may hold other things, and nothing here has any business with them.
 */
export async function pdfsIn(
	folder: FileSystemDirectoryHandle,
): Promise<string[]> {
	const names: string[] = [];
	for await (const entry of (folder as IterableDirectoryHandle).values()) {
		if (entry.kind === "file" && isPdfName(entry.name)) {
			names.push(entry.name);
		}
	}
	return names.sort((a, b) => a.localeCompare(b));
}

export async function writePdf(
	folder: FileSystemDirectoryHandle,
	name: string,
	contents: Blob,
): Promise<void> {
	if (!isPdfName(name)) {
		throw new Error(`Refusing to write ${name}.`);
	}

	const file = await folder.getFileHandle(name, { create: true });
	const writable = await file.createWritable();
	await writable.write(contents);
	await writable.close();
}

export async function removePdf(
	folder: FileSystemDirectoryHandle,
	name: string,
): Promise<void> {
	if (!isPdfName(name)) {
		throw new Error(`Refusing to delete ${name}.`);
	}
	await folder.removeEntry(name);
}
