const baseUrl =
	import.meta.env.VITE_API_URL ??
	(import.meta.env.DEV ? "http://localhost:8000" : undefined);

if (!baseUrl) {
	throw new Error(
		"VITE_API_URL must be set when building the frontend for production.",
	);
}

export class ApiError extends Error {
	readonly status: number;
	readonly data: unknown;

	constructor(status: number, data: unknown) {
		super(`Request to the API failed with status ${status}`);
		this.name = "ApiError";
		this.status = status;
		this.data = data;
	}
}

const parse = (body: string): unknown => {
	if (!body) return null;
	try {
		return JSON.parse(body);
	} catch {
		return body;
	}
};

export const fetcher = async <T>(
	url: string,
	options: RequestInit,
): Promise<T> => {
	const response = await fetch(`${baseUrl}${url}`, {
		...options,
		credentials: "include",
	});

	const data = parse(await response.text());

	if (!response.ok) {
		throw new ApiError(response.status, data);
	}

	return { status: response.status, data, headers: response.headers } as T;
};
