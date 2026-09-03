/**
 * Copies the built app into the desktop bundle.
 *
 * The renderer is packages/ui, built by React Router — the same static bundle
 * the browser deployment serves through nginx. This puts a copy where the
 * app:// handler expects to find it, so the packaged application carries the
 * app rather than reaching outside itself for it.
 *
 * Node's own copy rather than cp -r: the packaging runners include Windows.
 */

import { cpSync, existsSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const built = join(here, "..", "..", "..", "packages", "ui", "build", "client");
const staged = join(here, "..", "dist", "renderer");

if (!existsSync(built)) {
	console.error(
		`No built app at ${built}.\nRun "bun run build:web" first — the desktop bundles it, it does not build it.`,
	);
	process.exit(1);
}

rmSync(staged, { recursive: true, force: true });
cpSync(built, staged, { recursive: true });

console.log(`renderer staged from ${built}`);
