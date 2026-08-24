import { useMemo, useState } from "react";
import { useParams } from "react-router";
import { $api } from "@api/api";
import { Button } from "@components/button";
import { ResumePreview } from "~/components/resume-preview";
import { serializeToTex } from "~/lib/latex/serialize";

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

export default function ResumeRoute() {
	const { resumeId = "" } = useParams();

	const { data, isPending, isError } = $api.useQuery(
		"get",
		"/resumes/{resume_id}/document",
		{ params: { path: { resume_id: resumeId } } },
	);

	const [compiling, setCompiling] = useState(false);
	const [error, setError] = useState<string | null>(null);

	// the source is derived, never stored; regenerating it is far cheaper than
	// keeping it in sync with the document
	const tex = useMemo(() => (data ? serializeToTex(data) : ""), [data]);

	const slug =
		data?.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase() || "resume";

	/**
	 * Fetched directly rather than through the generated client, which parses
	 * every response as JSON. This one is a PDF.
	 */
	async function downloadPdf() {
		setCompiling(true);
		setError(null);

		try {
			const response = await fetch(`${API_BASE_URL}/resumes/${resumeId}/pdf`, {
				method: "POST",
				credentials: "include",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ source: tex }),
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

	if (isPending) {
		return <p className="p-8 text-ink-subtle text-sm">Loading resume…</p>;
	}

	if (isError || !data) {
		return (
			<p className="p-8 text-ink-subtle text-sm">Could not load this resume.</p>
		);
	}

	return (
		<main className="min-h-screen">
			<div className="mx-auto flex max-w-[8.5in] flex-wrap items-center gap-3 p-4 print:hidden">
				<h1 className="mr-auto text-lg font-semibold">{data.title}</h1>

				<Button
					onClick={() =>
						save(`${slug}.tex`, tex, "application/x-tex;charset=utf-8")
					}
					variant="secondary"
				>
					Download .tex
				</Button>

				<Button disabled={compiling} onClick={downloadPdf}>
					{compiling ? "Building PDF…" : "Download PDF"}
				</Button>
			</div>

			{error && (
				<div className="mx-auto mb-4 max-w-[8.5in] px-4 print:hidden">
					<p
						className="rounded-xl bg-negative-bg px-4 py-2 text-negative text-sm"
						role="alert"
					>
						{error}
					</p>
				</div>
			)}

			<div className="flex justify-center pb-12 print:p-0">
				<div className="relative origin-top shadow-lg print:shadow-none">
					<ResumePreview document={data} />
					{/* shows where page one ends, before anyone bothers compiling */}
					<div className="resume-page-break print:hidden" />
				</div>
			</div>
		</main>
	);
}
