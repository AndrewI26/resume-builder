import { $api } from "@api/api";
import { Button } from "@components/button";
import { ResumeEditor } from "@components/resume-editor";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router";
import { ResumePreview } from "~/components/resume-preview";
import { serializeToTex } from "~/lib/latex/serialize";
import {
	buildDocument,
	type Catalogs,
	isDirty,
	type ResumeDraft,
} from "~/lib/resume/document";
import type { SectionType } from "~/lib/resume/types";

const API_BASE_URL =
	import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function save(filename: string, contents: Blob | string, type?: string) {
	const blob =
		typeof contents === "string" ? new Blob([contents], { type }) : contents;
	const url = URL.createObjectURL(blob);

	const link = document.createElement("a");
	link.href = url;
	link.download = filename;
	link.click();

	URL.revokeObjectURL(url);
}

/**
 * Everything the user could attach, fetched once for the editor.
 *
 * The document endpoint returns only what is already on the resume, so the
 * catalogs are what make swapping and adding possible without a round trip per
 * change — and they carry the full rows, so the preview can render something
 * the moment it is attached.
 */
function useCatalogs(): { catalogs: Catalogs; isPending: boolean } {
	const education = $api.useQuery("get", "/education/");
	const experience = $api.useQuery("get", "/experience/");
	const project = $api.useQuery("get", "/project/");
	const skill = $api.useQuery("get", "/skill/");

	return useMemo(
		() => ({
			catalogs: {
				education: education.data ?? [],
				experience: experience.data ?? [],
				project: project.data ?? [],
				skill: skill.data ?? [],
			} as Catalogs,
			isPending:
				education.isPending ||
				experience.isPending ||
				project.isPending ||
				skill.isPending,
		}),
		[
			education.data,
			education.isPending,
			experience.data,
			experience.isPending,
			project.data,
			project.isPending,
			skill.data,
			skill.isPending,
		],
	);
}

/** What the preview is and is not, stated where someone will read it. */
function PreviewNotice() {
	return (
		<p className="mx-auto mb-3 max-w-[8.5in] rounded-xl bg-field px-4 py-2 text-ink-subtle text-sm">
			<span className="font-semibold text-ink">Approximate preview.</span> This
			is an HTML stand-in drawn to the template's own measurements. TeX breaks
			lines, hyphenates and kerns differently, so the compiled PDF will differ
			in places — usually where a line wraps. Download the PDF for the real
			thing.
		</p>
	);
}

export default function ResumeRoute() {
	const { resumeId = "" } = useParams();
	const queryClient = useQueryClient();

	const resume = $api.useQuery("get", "/resumes/{resume_id}", {
		params: { path: { resume_id: resumeId } },
	});
	const membership = $api.useQuery("get", "/resumes/{resume_id}/sections", {
		params: { path: { resume_id: resumeId } },
	});
	const personalInfo = $api.useQuery("get", "/personal-info/");
	const { catalogs } = useCatalogs();

	const { mutateAsync: saveResume } = $api.useMutation(
		"put",
		"/resumes/{resume_id}",
	);
	const { mutateAsync: saveSections } = $api.useMutation(
		"put",
		"/resumes/{resume_id}/sections",
	);

	// what the server last told us, and what the user has done to it since
	const saved: ResumeDraft | null = useMemo(() => {
		if (!resume.data || !membership.data) {
			return null;
		}

		return {
			order: (resume.data.section_order ?? []) as SectionType[],
			sections: membership.data.sections,
		};
	}, [resume.data, membership.data]);

	const [draft, setDraft] = useState<ResumeDraft | null>(null);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [compiling, setCompiling] = useState(false);

	// adopt the server's state once, and again whenever a save re-fetches it
	useEffect(() => {
		if (saved !== null && draft === null) {
			setDraft(saved);
		}
	}, [saved, draft]);

	const info = useMemo(
		() =>
			(personalInfo.data ?? []).find(
				(row) => row.id === resume.data?.personal_info_id,
			) ?? null,
		[personalInfo.data, resume.data?.personal_info_id],
	);

	const preview = useMemo(() => {
		if (!resume.data || draft === null) {
			return null;
		}

		return buildDocument({
			id: resumeId,
			title: resume.data.title,
			template: resume.data.template,
			fullName: resume.data.full_name ?? "",
			personalInfo: info,
			draft,
			catalogs,
		});
	}, [resume.data, draft, catalogs, info, resumeId]);

	const tex = useMemo(
		() => (preview ? serializeToTex(preview) : ""),
		[preview],
	);

	const slug =
		resume.data?.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase() || "resume";

	const dirty = draft !== null && saved !== null && isDirty(draft, saved);

	async function persist() {
		if (draft === null || !resume.data) {
			return;
		}

		setSaving(true);
		setError(null);

		try {
			// order lives on the resume, membership in the join table; both have to
			// land for the page to look like the panel says it will
			await saveResume({
				params: { path: { resume_id: resumeId } },
				body: {
					title: resume.data.title,
					template: resume.data.template,
					full_name: resume.data.full_name,
					personal_info_id: resume.data.personal_info_id,
					section_order: draft.order,
				},
			});
			await saveSections({
				params: { path: { resume_id: resumeId } },
				body: { sections: draft.sections },
			});

			await Promise.all([
				queryClient.invalidateQueries({
					queryKey: $api.queryOptions("get", "/resumes/{resume_id}", {
						params: { path: { resume_id: resumeId } },
					}).queryKey,
				}),
				queryClient.invalidateQueries({
					queryKey: $api.queryOptions("get", "/resumes/{resume_id}/sections", {
						params: { path: { resume_id: resumeId } },
					}).queryKey,
				}),
				queryClient.invalidateQueries({
					queryKey: $api.queryOptions("get", "/resumes/{resume_id}/document", {
						params: { path: { resume_id: resumeId } },
					}).queryKey,
				}),
			]);
		} catch {
			setError("Could not save the changes. Please try again.");
		} finally {
			setSaving(false);
		}
	}

	/**
	 * Fetched directly rather than through the generated client, which parses
	 * every response as JSON. This one is a PDF.
	 */
	async function downloadPdf() {
		setCompiling(true);
		setError(null);

		try {
			// the worker builds the document from the saved rows, so anything still
			// only in the draft would not appear in the file
			if (dirty) {
				await persist();
			}

			const response = await fetch(`${API_BASE_URL}/resumes/${resumeId}/pdf`, {
				method: "POST",
				credentials: "include",
			});

			if (!response.ok) {
				// a 422 carries the engine's own complaint, which is worth showing
				const detail = await response
					.json()
					.then((body) => body.detail)
					.catch(() => null);

				throw new Error(
					typeof detail === "string" && detail
						? detail
						: "Could not build the PDF. Please try again.",
				);
			}

			save(`${slug}.pdf`, await response.blob());
		} catch (caught) {
			setError(
				caught instanceof Error
					? caught.message
					: "Could not build the PDF. Please try again.",
			);
		} finally {
			setCompiling(false);
		}
	}

	if (resume.isPending || membership.isPending) {
		return <p className="p-8 text-ink-subtle text-sm">Loading resume…</p>;
	}

	if (resume.isError || !resume.data || preview === null || draft === null) {
		return (
			<p className="p-8 text-ink-subtle text-sm">Could not load this resume.</p>
		);
	}

	return (
		<main className="min-h-screen">
			<div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-3 p-4 print:hidden">
				<h1 className="mr-auto font-semibold text-lg">{resume.data.title}</h1>

				{dirty && (
					<span className="text-ink-subtle text-sm">Unsaved changes</span>
				)}

				<Button
					disabled={!dirty || saving}
					onClick={persist}
					variant="secondary"
				>
					{saving ? "Saving…" : "Save changes"}
				</Button>

				<Button
					onClick={() =>
						save(`${slug}.tex`, tex, "application/x-tex;charset=utf-8")
					}
					variant="secondary"
				>
					Download .tex
				</Button>

				<Button disabled={compiling || saving} onClick={downloadPdf}>
					{compiling ? "Building PDF…" : "Download PDF"}
				</Button>
			</div>

			{error && (
				<div className="mx-auto mb-4 max-w-[1400px] px-4 print:hidden">
					<p
						className="rounded-xl bg-negative-bg px-4 py-2 text-negative text-sm"
						role="alert"
					>
						{error}
					</p>
				</div>
			)}

			<div className="mx-auto flex max-w-[1400px] flex-col gap-6 px-4 pb-12 lg:flex-row lg:items-start print:block print:p-0">
				<aside className="w-full shrink-0 lg:sticky lg:top-4 lg:w-[22rem] print:hidden">
					<h2 className="mb-3 font-semibold text-sm">Sections</h2>
					<ResumeEditor catalogs={catalogs} draft={draft} onChange={setDraft} />
				</aside>

				<div className="min-w-0 flex-1">
					<PreviewNotice />
					<div className="flex justify-center print:block">
						<div className="relative origin-top shadow-lg print:shadow-none">
							<ResumePreview document={preview} />
							{/* shows where page one ends, before anyone bothers compiling */}
							<div className="resume-page-break print:hidden" />
						</div>
					</div>
				</div>
			</div>
		</main>
	);
}
