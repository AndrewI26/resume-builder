/**
 * The only thing the window learns about the machine it is running on.
 *
 * The renderer is the same bundle a browser loads and is treated with the same
 * suspicion: context isolation is on, Node is off, and what crosses this
 * boundary is two strings. They cannot be baked into the bundle because
 * neither exists until the app launches — the port is chosen at runtime and
 * the token is generated per run.
 *
 * `packages/ui/app/platform/host.ts` is the other side of this.
 */

import { contextBridge } from "electron";

contextBridge.exposeInMainWorld("resumeBuilderHost", {
	apiBaseUrl: process.env.RESUME_BUILDER_API_URL,
	apiToken: process.env.RESUME_BUILDER_API_TOKEN,
});
