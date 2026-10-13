import type { components } from "@api/schema.d.ts";
import { Button } from "@components/button";
import { ConfirmDialog } from "@components/confirm-dialog";
import { useEffect, useState } from "react";
import { compileResumePdf } from "~/lib/export/compile";
import { filenames } from "~/lib/export/filenames";
import {
	canExportToFolder,
	pdfsIn,
	pickFolder,
	removePdf,
	writePdf,
} from "~/lib/export/folder";
import { zip } from "~/lib/export/zip";

type Resume = components["schemas"]["ResumeRead"];

const ZIP_FILENAME = "resumes.zip";

/** What exporting into a chosen folder is about to do, for the confirmation. */
type FolderPlan = {
	folder: FileSystemDirectoryHandle;
	resumes: Resume[];
	names: string[];
	// PDFs already there that no resume will write: these are deleted
	stale: string[];
};

type Failure = { id: string; title: string; reason: string };

type Report = {
	saved: number;
	deleted: number;
	failures: Failure[];
	where: string;
};

/** The order every exporter uses, so a repeated title gets the same number. */
function byTitle(resumes: Resume[]): Resume[] {
	return [...resumes].sort((a, b) => a.title.localeCompare(b.title));
}

function listNames(names: string[], limit = 6): string {
	const shown = names.slice(0, limit).join(", ");
	return names.length > limit
		? `${shown} and ${names.length - limit} more`
		: shown;
}

function reportLine(report: Report): string {
	const saved = `Saved ${report.saved} PDF${report.saved === 1 ? "" : "s"} ${report.where}`;
	const deleted =
		report.deleted > 0
			? `, and deleted ${report.deleted} old PDF${report.deleted === 1 ? "" : "s"}`
			: "";
	return `${saved}${deleted}.`;
}

/**
 * Compiles every resume and saves the PDFs together, like the desktop app's
 * export: into a folder the person picks, replacing the PDFs already in it,
 * where the browser can write to a folder (Chrome and Edge), and as one ZIP
 * download everywhere else.
 *
 * Resumes compile one at a time. Each is a LaTeX run on the server, and
 * several at once would only queue there.
 */
export function ExportPdfs({ resumes }: { resumes: Resume[] }) {
	// decided after mounting: the page is prerendered, where there is no window
	const [folderSupported, setFolderSupported] = useState(false);
	const [plan, setPlan] = useState<FolderPlan | null>(null);
	const [progress, setProgress] = useState<string | null>(null);
	const [report, setReport] = useState<Report | null>(null);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		setFolderSupported(canExportToFolder());
	}, []);

	const running = progress !== null;

	/** Compile each resume in turn, handing each PDF to `save`. */
	const compileAll = async (
		ordered: Resume[],
		save: (index: number, pdf: Blob) => Promise<void>,
	): Promise<Failure[]> => {
		const failures: Failure[] = [];
		for (const [index, resume] of ordered.entries()) {
			setProgress(
				`Building ${index + 1} of ${ordered.length}: ${resume.title}`,
			);
			let pdf: Blob;
			try {
				pdf = await compileResumePdf(resume.id);
			} catch (caught) {
				failures.push({
					id: resume.id,
					title: resume.title,
					reason: caught instanceof Error ? caught.message : String(caught),
				});
				continue;
			}
			// a save that fails (the folder went away, permission was revoked)
			// would fail for every resume after it too, so it ends the run
			await save(index, pdf);
		}
		return failures;
	};

	const start = async () => {
		setError(null);
		setReport(null);

		if (!folderSupported) {
			await downloadZip();
			return;
		}

		try {
			const folder = await pickFolder();
			if (folder === null) {
				return;
			}
			const ordered = byTitle(resumes);
			const names = filenames(ordered.map((resume) => resume.title));
			const existing = await pdfsIn(folder);
			setPlan({
				folder,
				resumes: ordered,
				names,
				stale: existing.filter((name) => !names.includes(name)),
			});
		} catch (caught) {
			setError(
				caught instanceof Error
					? caught.message
					: "Could not open that folder.",
			);
		}
	};

	const exportToFolder = async (chosen: FolderPlan) => {
		setPlan(null);
		try {
			const written: string[] = [];
			const failures = await compileAll(chosen.resumes, async (index, pdf) => {
				await writePdf(chosen.folder, chosen.names[index], pdf);
				written.push(chosen.names[index]);
			});

			// Only once the new PDFs are in place. A resume that failed to build
			// keeps its old PDF rather than leaving a gap where it was.
			setProgress("Removing old PDFs");
			for (const name of chosen.stale) {
				await removePdf(chosen.folder, name);
			}

			setReport({
				saved: written.length,
				deleted: chosen.stale.length,
				failures,
				where: `to ${chosen.folder.name}`,
			});
		} catch (caught) {
			setError(
				`Could not save to that folder: ${
					caught instanceof Error ? caught.message : String(caught)
				}`,
			);
		} finally {
			setProgress(null);
		}
	};

	const downloadZip = async () => {
		try {
			const ordered = byTitle(resumes);
			const names = filenames(ordered.map((resume) => resume.title));
			const entries: { name: string; data: Uint8Array }[] = [];
			const failures = await compileAll(ordered, async (index, pdf) => {
				entries.push({
					name: names[index],
					data: new Uint8Array(await pdf.arrayBuffer()),
				});
			});

			if (entries.length > 0) {
				const url = URL.createObjectURL(zip(entries));
				const anchor = document.createElement("a");
				anchor.href = url;
				anchor.download = ZIP_FILENAME;
				anchor.click();
				URL.revokeObjectURL(url);
			}

			setReport({
				saved: entries.length,
				deleted: 0,
				failures,
				where: `in ${ZIP_FILENAME}`,
			});
		} catch (caught) {
			setError(caught instanceof Error ? caught.message : String(caught));
		} finally {
			setProgress(null);
		}
	};

	if (resumes.length === 0) {
		return null;
	}

	return (
		<div className="mt-6 flex flex-col items-start gap-2">
			<div className="flex flex-wrap items-center gap-3">
				<Button disabled={running} onClick={start} variant="secondary">
					{folderSupported
						? "Export all PDFs to a folder"
						: "Download all PDFs"}
				</Button>
				{progress !== null && (
					<span className="text-ink-subtle text-sm" role="status">
						{progress}…
					</span>
				)}
			</div>

			{!folderSupported && !running && report === null && (
				<p className="text-ink-subtle text-sm">
					Downloads one ZIP. In Chrome or Edge you can save straight into a
					folder instead.
				</p>
			)}

			{report !== null && (
				<div
					className="rounded-xl bg-field px-4 py-2 text-ink text-sm"
					role="status"
				>
					{reportLine(report)}
					{report.failures.length > 0 && (
						<>
							{" "}
							{report.failures.length} couldn't be built:
							<ul className="mt-1 list-disc pl-5">
								{report.failures.map((failure) => (
									<li key={failure.id}>
										{failure.title}: {failure.reason}
									</li>
								))}
							</ul>
						</>
					)}
				</div>
			)}

			{error !== null && (
				<p
					className="rounded-xl bg-negative-bg px-4 py-2 text-negative text-sm"
					role="alert"
				>
					{error}
				</p>
			)}

			<ConfirmDialog
				confirmLabel={plan?.stale.length ? "Replace PDFs" : "Export"}
				description={
					plan === null ? null : (
						<>
							<p>
								Saves {plan.resumes.length} PDF
								{plan.resumes.length === 1 ? "" : "s"} into{" "}
								<span className="text-ink">{plan.folder.name}</span>, replacing
								any with the same name.
							</p>
							{plan.stale.length > 0 ? (
								<p className="mt-2">
									This permanently deletes {plan.stale.length} other PDF
									{plan.stale.length === 1 ? "" : "s"} in the folder:{" "}
									<span className="text-ink">{listNames(plan.stale)}</span>.
									Files that aren't PDFs, and anything in subfolders, are left
									alone.
								</p>
							) : (
								<p className="mt-2">
									No other PDFs in the folder will be deleted.
								</p>
							)}
						</>
					)
				}
				onCancel={() => setPlan(null)}
				onConfirm={() => {
					if (plan !== null) {
						exportToFolder(plan);
					}
				}}
				open={plan !== null}
				title="Export all PDFs?"
			/>
		</div>
	);
}
