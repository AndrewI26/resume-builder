import { $api } from "@api/api";
import { Button } from "@components/button";
import { PdfPreview, type PdfState } from "@components/pdf-preview";
import { ResumeEditor } from "@components/resume-editor";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router";
import { serializeToTex } from "~/lib/latex/serialize";
import {
	buildDocument,
	type Catalogs,
	isDirty,
	type ResumeDraft,
	signature,
} from "~/lib/resume/document";
import type { SectionType } from "~/lib/resume/types";

const API_BASE_URL =
	import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/** How long editing has to pause before the draft is written back. */
const AUTOSAVE_DELAY_MS = 800;

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

const TIME = new Intl.DateTimeFormat(undefined, {
	hour: "numeric",
	minute: "2-digit",
});

/**
 * What the autosave is doing, where the save button used to be.
 *
 * Editing writes itself back, so the only thing worth saying is whether the
 * work is safe. A failure is the one state that needs a control, because it is
 * the one the page cannot resolve on its own.
 */
function SaveStatus({
	dirty,
	failed,
	onRetry,
	savedAt,
	saving,
}: {
	dirty: boolean;
	failed: boolean;
	onRetry: () => void;
	savedAt: Date | null;
	saving: boolean;
}) {
	if (failed) {
		return (
			<span className="flex items-center gap-2 text-negative text-sm">
				Could not save
				<button
					className="underline underline-offset-2 hover:opacity-70"
					onClick={onRetry}
					type="button"
				>
					Retry
				</button>
			</span>
		);
	}

	if (saving) {
		return <span className="text-ink-subtle text-sm">Saving…</span>;
	}

	if (dirty) {
		return <span className="text-ink-subtle text-sm">Unsaved changes</span>;
	}

	return (
		<span className="text-ink-subtle text-sm">
			{savedAt ? `Saved ${TIME.format(savedAt)}` : "All changes saved"}
		</span>
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
	const [savedAt, setSavedAt] = useState<Date | null>(null);
	const [saveError, setSaveError] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [compiling, setCompiling] = useState(false);
	const [pdf, setPdf] = useState<PdfState | null>(null);

	// object URLs outlive the render that made them, so the previous one has to
	// be released by hand or every recompile leaks a copy of the file
	const objectUrl = useRef<string | null>(null);
	// the draft an in-flight save is carrying, so a pending write is not re-sent
	const submitted = useRef<string | null>(null);
	useEffect(
		() => () => {
			if (objectUrl.current) {
				URL.revokeObjectURL(objectUrl.current);
			}
		},
		[],
	);

	// adopt the server's state once, and again whenever a save re-fetches it
	useEffect(() => {
		if (saved !== null && draft === null) {
			setDraft(saved);
		}
	}, [saved, draft]);

	/**
	 * Save on a pause in editing.
	 *
	 * Dragging a row fires a change per frame, so the wait is what turns a
	 * gesture into one request instead of dozens. `submitted` remembers which
	 * draft is already on its way: the server's copy does not catch up until
	 * the refetch lands, so without it the same save would fire again in the
	 * gap and the two would race.
	 */
	const persistRef = useRef(persist);
	persistRef.current = persist;

	useEffect(() => {
		if (draft === null || saved === null || !isDirty(draft, saved)) {
			return;
		}

		if (submitted.current === signature(draft)) {
			return;
		}

		const timer = setTimeout(() => {
			void persistRef.current();
		}, AUTOSAVE_DELAY_MS);

		return () => clearTimeout(timer);
	}, [draft, saved]);

	// compile once on arrival so the page opens with the resume on it rather
	// than an empty frame and a button. Guarded by a ref instead of the pdf
	// state so a failed compile does not retry on every render.
	const compiled = useRef(false);
	useEffect(() => {
		if (draft !== null && !compiled.current) {
			compiled.current = true;
			void compile();
		}
	});

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

	// the PDF was typeset from whatever the draft said at the time; once the
	// panel moves on, what is on screen is a picture of the past
	const stale =
		draft !== null && pdf !== null && pdf.signature !== signature(draft);

	async function persist(): Promise<boolean> {
		if (draft === null || !resume.data) {
			return false;
		}

		setSaving(true);
		setSaveError(false);
		submitted.current = signature(draft);

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
			setSavedAt(new Date());
			return true;
		} catch {
			// let the next edit — or the retry — try again
			submitted.current = null;
			setSaveError(true);
			return false;
		} finally {
			setSaving(false);
		}
	}

	/**
	 * Typeset the resume and keep the result in the page.
	 *
	 * Fetched directly rather than through the generated client, which parses
	 * every response as JSON. This one is a PDF.
	 *
	 * The worker builds the document from the saved rows, so an unsaved draft
	 * has to land first or the compile would faithfully render the old version.
	 */
	async function compile() {
		if (draft === null) {
			return;
		}

		setCompiling(true);
		setError(null);

		try {
			if (dirty && !(await persist())) {
				return;
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

			const blob = await response.blob();

			if (objectUrl.current) {
				URL.revokeObjectURL(objectUrl.current);
			}
			const url = URL.createObjectURL(blob);
			objectUrl.current = url;

			setPdf({ url, blob, signature: signature(draft) });
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

	/** Saves the file already in the page — no second trip to the compiler. */
	function downloadPdf() {
		if (pdf !== null) {
			save(`${slug}.pdf`, pdf.blob);
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
			<div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-3 p-4">
				<h1 className="mr-auto font-semibold text-lg">{resume.data.title}</h1>

				<SaveStatus
					dirty={dirty}
					onRetry={persist}
					failed={saveError}
					savedAt={savedAt}
					saving={saving}
				/>

				<Button
					onClick={() =>
						save(`${slug}.tex`, tex, "application/x-tex;charset=utf-8")
					}
					variant="secondary"
				>
					Download .tex
				</Button>
			</div>

			<div className="mx-auto flex max-w-[1400px] flex-col gap-6 px-4 pb-12 lg:flex-row lg:items-start">
				<aside className="w-full shrink-0 lg:sticky lg:top-4 lg:w-[22rem]">
					<h2 className="mb-3 font-semibold text-sm">Sections</h2>
					<ResumeEditor catalogs={catalogs} draft={draft} onChange={setDraft} />
				</aside>

				<div className="flex min-w-0 flex-1 flex-col">
					<PdfPreview
						compiling={compiling}
						error={error}
						onDownload={downloadPdf}
						onRecompile={compile}
						pdf={pdf}
						stale={stale}
					/>
				</div>
			</div>
		</main>
	);
}
