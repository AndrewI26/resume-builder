/**
 * The file a resume is saved as.
 *
 * Mirrors `slug` / `filenames` in the export script
 * (apps/api/scripts/export_resumes.py) and the desktop app
 * (apps/desktop/src/export.rs), so a folder written by any of them has the
 * same names in it: each character that isn't a letter or digit becomes a
 * hyphen, and a repeated name is numbered from 2.
 */
export function slug(title: string): string {
	const stem = Array.from(title, (character) =>
		/[\p{L}\p{N}]/u.test(character) ? character : "-",
	)
		.join("")
		.replace(/^-+|-+$/g, "")
		.toLowerCase();

	return stem || "resume";
}

export function filenames(titles: string[]): string[] {
	const seen = new Map<string, number>();

	return titles.map((title) => {
		const stem = slug(title);
		const count = (seen.get(stem) ?? 0) + 1;
		seen.set(stem, count);
		return count === 1 ? `${stem}.pdf` : `${stem}-${count}.pdf`;
	});
}

export function isPdfName(name: string): boolean {
	return /^[^/\\]+\.pdf$/i.test(name) && name.toLowerCase() !== ".pdf";
}
