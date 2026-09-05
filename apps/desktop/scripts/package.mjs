/**
 * Packages the installer, the same way the release workflow does.
 *
 * On macOS that is deliberately two passes with a signing step wedged between
 * them, rather than the single electron-builder run every other platform gets.
 * The app has to be ad-hoc signed after packaging or macOS calls it damaged,
 * and neither an electron-builder hook nor mac.identity can do it — the long
 * version of why is in scripts/adhoc-sign-mac.sh.
 *
 * This exists so that "bun run package:desktop" produces the same artifact as
 * CI. When it was a plain electron-builder call it did not: a locally packaged
 * app was unsigned and refused to open, which reads as the signing fix having
 * failed rather than as never having run.
 *
 * Node rather than a shell script, because this one runs on Windows too.
 */

import { spawnSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const desktop = join(here, "..");
const release = join(desktop, "release");

// Whatever the caller added, e.g. `--x64`. Forwarded to every pass.
const extra = process.argv.slice(2);

function run(command, args) {
	const result = spawnSync(command, args, {
		cwd: desktop,
		stdio: "inherit",
		shell: process.platform === "win32",
		// Stops electron-builder hunting the keychain for a Developer ID that is
		// not there. The signing step below does the sealing instead.
		env: { ...process.env, CSC_IDENTITY_AUTO_DISCOVERY: "false" },
	});

	if (result.error) {
		throw result.error;
	}
	if (result.status !== 0) {
		process.exit(result.status ?? 1);
	}
}

const builder = ["electron-builder", "--config", "electron-builder.yml"];

if (process.platform !== "darwin") {
	run("bunx", [...builder, ...extra]);
	process.exit(0);
}

// Pass one: the .app, with no installer around it yet.
run("bunx", [...builder, "--mac", "--dir", ...extra]);

// electron-builder names the directory after the arch — release/mac for x64,
// release/mac-arm64 for arm64 — so look for the bundle rather than reproducing
// that rule here.
const app = readdirSync(release, { withFileTypes: true })
	.filter((entry) => entry.isDirectory() && entry.name.startsWith("mac"))
	.flatMap((entry) =>
		readdirSync(join(release, entry.name))
			.filter((name) => name.endsWith(".app"))
			.map((name) => join(release, entry.name, name)),
	)
	.at(0);

if (!app) {
	console.error(`No .app under ${release} after packaging.`);
	process.exit(1);
}

run(join(here, "adhoc-sign-mac.sh"), [app]);

// Pass two: the dmg, built around the bundle that was just sealed.
run("bunx", [
	...builder,
	"--mac",
	"dmg",
	"--prepackaged",
	app,
	"--publish",
	"never",
	...extra,
]);
