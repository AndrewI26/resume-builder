import type { components } from "@api/schema.d.ts";

type ValidationError = components["schemas"]["HTTPValidationError"];

/**
 * One readable line per problem in a rejected import.
 *
 * Field errors carry their location, which reads as a path into the file
 * (`projects[0].name`).
 */
export function importProblems(error: unknown): string[] {
	const detail = (error as Partial<ValidationError> | { detail?: string })
		?.detail;

	if (typeof detail === "string") {
		return [detail];
	}
	if (!Array.isArray(detail) || detail.length === 0) {
		return ["Could not import that file. Try again."];
	}

	return detail.map((item) => {
		const path = formatPath(item.loc);
		return path === "" ? item.msg : `${path}: ${item.msg}`;
	});
}

function formatPath(loc: (string | number)[]): string {
	return loc
		.filter((part, index) => !(index === 0 && part === "body"))
		.reduce<string>((path, part) => {
			if (typeof part === "number") {
				return `${path}[${part}]`;
			}
			return path === "" ? part : `${path}.${part}`;
		}, "");
}
