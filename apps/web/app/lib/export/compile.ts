import { apiBaseUrl } from "~/platform/host";

/**
 * Compile one saved resume to a PDF.
 *
 * Outside the typed client because the response is a file rather than JSON.
 * A failure is thrown with the most useful line of the reason: the engine's
 * own complaint runs to pages, and its last line names the problem.
 */
export async function compileResumePdf(resumeId: string): Promise<Blob> {
	const response = await fetch(`${apiBaseUrl}/resumes/${resumeId}/pdf`, {
		method: "POST",
		credentials: "include",
	});

	if (!response.ok) {
		const detail = await response
			.json()
			.then((body) => body.detail)
			.catch(() => null);
		const lastLine =
			typeof detail === "string" ? detail.trim().split("\n").pop() : "";
		throw new Error(lastLine || "Could not build the PDF.");
	}

	return response.blob();
}
