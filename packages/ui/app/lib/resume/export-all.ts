/**
 * Exporting every resume to a folder on the machine.
 *
 * This is the desktop counterpart to `scripts/export_resumes.py`, and it
 * deliberately produces the same folder: the same names, from the same titles,
 * with the same numbering when two resumes are called the same thing. Someone
 * who has used the script should not be able to tell which one made a folder.
 *
 * It compiles through the ordinary per-resume endpoint rather than anything
 * new. That endpoint already typesets from the saved rows, reports what the
 * engine objected to, and on a desktop install does the work in-process
 * without a queue — so a bulk export is that request in a loop, and the only
 * thing missing was somewhere to put the files.
 *
 * One at a time, on purpose. Typesetting is CPU-bound and the sidecar compiles
 * in the process serving the request; firing twenty at once would not finish
 * sooner, and would leave the window unable to do anything else meanwhile.
 */

import { apiBaseUrl, apiHeaders } from "~/platform/host";

/** The shell functions this needs; see `fileExporter` in platform/host. */
type Exporter = {
	writeExportedPdf: (
		directory: string,
		filename: string,
		contents: Uint8Array,
	) => Promise<void>;
};

export type ExportableResume = { id: string; title: string };

/** A resume that would not compile, kept so the run can report it at the end. */
export type ExportFailure = { title: string; reason: string };

export type ExportOutcome = {
	written: number;
	failures: ExportFailure[];
};

/**
 * A safe file stem for a resume's title.
 *
 * Matches what `/resumes/{id}/pdf` sends as a download name, so a file exported
 * here is named the same as one saved from the resume screen.
 */
function slug(title: string): string {
	// One hyphen per replaced character rather than one per run, because that
	// is what the script and the endpoint both do — "C++ / Rust" becomes
	// "c------rust" for all three of them. Collapsing the runs here would read
	// better and be a different filename, which is worse.
	const stem = [...title]
		.map((character) => (/[\p{L}\p{N}]/u.test(character) ? character : "-"))
		.join("")
		.replace(/^-+|-+$/g, "");

	return stem.toLowerCase() || "resume";
}

/**
 * One `.pdf` name per title, in order, with collisions numbered.
 *
 * Titles are not unique — a person can have two resumes both called "Backend"
 * — and letting one overwrite the other would drop an export without saying
 * so. The first keeps the plain name and the rest are numbered from two, which
 * is what the script does.
 */
export function exportFilenames(titles: string[]): string[] {
	const seen = new Map<string, number>();

	return titles.map((title) => {
		const stem = slug(title);
		const count = seen.get(stem) ?? 0;
		seen.set(stem, count + 1);
		return count === 0 ? `${stem}.pdf` : `${stem}-${count + 1}.pdf`;
	});
}

/** What the API said went wrong, when it bothered to say. */
async function failureReason(response: Response): Promise<string> {
	const detail = await response
		.json()
		.then((body) => body.detail)
		.catch(() => null);

	if (typeof detail === "string" && detail) {
		// A 422 carries the engine's own complaint, which runs to pages; the
		// last line is the part that names the problem.
		return detail.trim().split("\n").at(-1) ?? detail;
	}

	return `the server answered ${response.status}`;
}

/**
 * Compile every resume and write it into `directory`.
 *
 * A resume that will not export is recorded and skipped rather than abandoning
 * the ones queued behind it — the same choice the script makes, for the same
 * reason: nineteen good resumes are worth having when the twentieth is broken.
 * A folder that cannot be written to is different, and stops the run, because
 * every remaining resume would fail the same way.
 *
 * `onProgress` is called before each compile so the screen can name what it is
 * working on; a bulk export is slow enough that silence reads as a hang.
 */
export async function exportAllResumes(
	resumes: ExportableResume[],
	directory: string,
	exporter: Exporter,
	onProgress?: (completed: number, total: number, title: string) => void,
): Promise<ExportOutcome> {
	const names = exportFilenames(resumes.map((resume) => resume.title));
	const failures: ExportFailure[] = [];
	let written = 0;

	for (const [index, resume] of resumes.entries()) {
		onProgress?.(index, resumes.length, resume.title);

		let pdf: ArrayBuffer;
		try {
			// Outside the typed client because the response is a file rather
			// than JSON, so it carries the same headers by hand.
			const response = await fetch(`${apiBaseUrl}/resumes/${resume.id}/pdf`, {
				method: "POST",
				credentials: "include",
				headers: apiHeaders(),
			});

			if (!response.ok) {
				failures.push({
					title: resume.title,
					reason: await failureReason(response),
				});
				continue;
			}

			pdf = await response.arrayBuffer();
		} catch (error) {
			failures.push({
				title: resume.title,
				reason:
					error instanceof Error ? error.message : "the export could not run",
			});
			continue;
		}

		// Not caught alongside the compile: a refused write is about the folder,
		// not this resume, and carrying on would just fail once per resume.
		await exporter.writeExportedPdf(
			directory,
			names[index],
			new Uint8Array(pdf),
		);
		written += 1;
	}

	onProgress?.(resumes.length, resumes.length, "");
	return { written, failures };
}
