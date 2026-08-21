import { ApiError } from "./fetcher";

type Detail = { detail?: unknown };

export function apiErrorMessage(error: unknown, fallback: string): string {
	if (!(error instanceof ApiError)) return fallback;

	const detail = (error.data as Detail | null)?.detail;

	if (typeof detail === "string") return detail;

	if (Array.isArray(detail)) {
		const messages = detail
			.map((item) =>
				item && typeof item === "object" && "msg" in item ? item.msg : null,
			)
			.filter((msg): msg is string => typeof msg === "string");

		if (messages.length > 0) return messages.join(". ");
	}

	return fallback;
}
