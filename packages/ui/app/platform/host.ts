/**
 * Where the app is running, and what follows from it.
 *
 * The same screens run in a browser tab and inside the desktop shell. In the
 * browser the API is a known address baked in at build time. On the desktop it
 * is a server the shell started a moment ago on a port it picked at random, so
 * the address cannot be known until the window opens — and every request has
 * to carry the secret proving it comes from this app rather than from
 * something else running on the same machine.
 *
 * Both facts arrive from the shell through its preload bridge. Everything
 * reads them from here rather than reaching for the global, so one place knows
 * the difference exists.
 */

/** What the desktop shell puts on the window. Absent in a browser. */
export type DesktopHost = {
	/** The sidecar's address, chosen when the app launched. */
	apiBaseUrl: string;
	/** Proves a request came from this window. */
	apiToken: string;
};

declare global {
	interface Window {
		resumeBuilderHost?: DesktopHost;
	}
}

const host: DesktopHost | undefined =
	typeof window === "undefined" ? undefined : window.resumeBuilderHost;

/** Running inside the desktop shell rather than a browser tab. */
export const isDesktop = host !== undefined;

/**
 * Whether there is a library on this machine that could be kept in step with
 * an account.
 *
 * Only the desktop has one. The browser app's data is already the account, so
 * there is nothing for it to sync with and the screens for doing so would be
 * asking about something that cannot happen.
 */
export const canSync = isDesktop;

export const apiBaseUrl: string =
	host?.apiBaseUrl ??
	import.meta.env.VITE_API_BASE_URL ??
	"http://localhost:8000";

/**
 * Headers every request to the API must carry.
 *
 * Empty in the browser, where the session is a cookie and the server is the
 * one this bundle was built against.
 */
export function apiHeaders(): Record<string, string> {
	return host ? { "x-sidecar-token": host.apiToken } : {};
}
