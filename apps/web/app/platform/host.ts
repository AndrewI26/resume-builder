/**
 * Where the API is.
 *
 * The app is a browser SPA that calls the API straight from the page, so the
 * address is baked in at build time. The desktop app is a separate, native
 * program (apps/desktop) and never loads this bundle.
 */
export const apiBaseUrl: string =
	import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
