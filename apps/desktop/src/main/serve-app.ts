/**
 * Serving the built app to the window.
 *
 * Not file:// — the app uses ordinary browser history, so /resumes/:id has to
 * be a URL the window can be at, and a file URL has no notion of a path that
 * is not a file. A custom scheme gives it a real origin as well, which is what
 * makes storage and fetch behave the way they do in a browser.
 *
 * The rule below is the same one docker/web/nginx.conf applies to the same
 * bundle: a request that names a real file gets that file, and anything else
 * is a route, so it gets index.html and the router works out the rest.
 */

import { protocol, net } from "electron";
import { existsSync, statSync } from "node:fs";
import { join, normalize } from "node:path";
import { pathToFileURL } from "node:url";

export const APP_SCHEME = "app";

/** The origin the window sits at. The host is a placeholder; only the path matters. */
export const APP_ORIGIN = `${APP_SCHEME}://bundle`;

/**
 * Must be called before the app is ready.
 *
 * Registering the scheme as standard is what gives it an origin and a normal
 * relative-path resolution; as secure, what stops the window being treated as
 * an insecure context, which would put fetch and storage into a mode the app
 * does not expect.
 */
export function registerAppScheme(): void {
	protocol.registerSchemesAsPrivileged([
		{
			scheme: APP_SCHEME,
			privileges: {
				standard: true,
				secure: true,
				supportFetchAPI: true,
			},
		},
	]);
}

export function serveAppFrom(root: string): void {
	protocol.handle(APP_SCHEME, (request) => {
		const { pathname } = new URL(request.url);

		// join collapses any ../ before it is resolved, and the check that the
		// result is still inside the bundle is what stops a crafted path
		// reading the rest of the disk
		const requested = join(root, normalize(decodeURIComponent(pathname)));
		const inside = requested.startsWith(root);
		const isFile =
			inside && existsSync(requested) && statSync(requested).isFile();

		const file = isFile ? requested : join(root, "index.html");

		return net.fetch(pathToFileURL(file).toString());
	});
}
