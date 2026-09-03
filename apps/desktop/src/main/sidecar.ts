/**
 * The API, running as a child of this window.
 *
 * The desktop app embeds the same FastAPI the hosted service runs, in local
 * mode: one SQLite file, nobody signed in, typesetting done in-process. It is
 * a separate process because it is Python, not because it is remote — it
 * listens on loopback and answers only this app.
 *
 * Two things here are less obvious than they look.
 *
 * The port is chosen at runtime, so nothing can be hard-coded: another program
 * may already hold whatever we picked as a default, and a resume tool that
 * refuses to open because a port is busy is indefensible. The renderer is told
 * the address once the server answers.
 *
 * The token exists because loopback is not private on a shared machine. Any
 * other program running as this person could otherwise read the entire library
 * by asking a server that has no sign-in.
 */

import { type ChildProcess, spawn } from "node:child_process";
import { createServer } from "node:net";
import { randomBytes } from "node:crypto";
import { app } from "electron";
import { existsSync } from "node:fs";
import { join } from "node:path";

export type Sidecar = {
	baseUrl: string;
	token: string;
	stop: () => void;
};

/** How long to wait for the server to answer before giving up on it. */
const STARTUP_TIMEOUT_MS = 30_000;
const POLL_INTERVAL_MS = 200;

/**
 * A port the operating system says is free.
 *
 * Racy in principle — something else could take it between this closing and
 * the sidecar binding — but the alternative is guessing, and the window
 * between the two is a few milliseconds.
 */
function freePort(): Promise<number> {
	return new Promise((resolve, reject) => {
		const server = createServer();
		server.on("error", reject);
		server.listen(0, "127.0.0.1", () => {
			const address = server.address();
			if (address === null || typeof address === "string") {
				server.close();
				reject(new Error("could not find a free port"));
				return;
			}

			const { port } = address;
			server.close(() => resolve(port));
		});
	});
}

/**
 * How to start the API, which differs between a packaged app and a checkout.
 *
 * Packaged, it is a single binary built by PyInstaller and shipped unpacked
 * beside the app. In development there is no such binary and no reason to
 * build one on every run, so uv runs the real source tree — which is also what
 * makes an edit to a router visible without repackaging anything.
 */
function command(port: number): { file: string; args: string[]; cwd?: string } {
	const bundled = join(process.resourcesPath, "api", "resume-api");

	if (app.isPackaged || existsSync(bundled)) {
		return { file: bundled, args: ["--port", String(port)] };
	}

	return {
		file: "uv",
		args: [
			"run",
			"uvicorn",
			"main:app",
			"--host",
			"127.0.0.1",
			"--port",
			String(port),
		],
		// getAppPath() is apps/desktop when this runs from a checkout
		cwd: join(app.getAppPath(), "..", "api"),
	};
}

/** Where the bundled TeX distribution's binaries are, if this build has one. */
function texliveBin(): string | undefined {
	const bundled = join(process.resourcesPath, "texlive", "bin");
	return existsSync(bundled) ? bundled : undefined;
}

async function waitUntilAnswering(
	baseUrl: string,
	token: string,
	child: ChildProcess,
): Promise<void> {
	const deadline = Date.now() + STARTUP_TIMEOUT_MS;

	while (Date.now() < deadline) {
		if (child.exitCode !== null || child.signalCode !== null) {
			throw new Error(`the API exited during startup (${child.exitCode})`);
		}

		try {
			const response = await fetch(`${baseUrl}/openapi.json`, {
				headers: { "x-sidecar-token": token },
			});
			if (response.ok) {
				return;
			}
		} catch {
			// not listening yet, which is the normal case for the first second
		}

		await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
	}

	throw new Error("the API did not start in time");
}

/**
 * Start the API and wait until it answers.
 *
 * Resolves with everything the renderer needs to talk to it, and a stop()
 * that must be called before the app quits — see the note there.
 */
export async function startSidecar(): Promise<Sidecar> {
	const port = await freePort();
	const token = randomBytes(32).toString("hex");
	const baseUrl = `http://127.0.0.1:${port}`;
	const { file, args, cwd } = command(port);

	const child = spawn(file, args, {
		cwd,
		env: {
			...process.env,
			MODE: "local",
			LOCAL_DATA_DIR: app.getPath("userData"),
			SIDECAR_TOKEN: token,
			...(texliveBin() ? { TEXLIVE_BIN: texliveBin() } : {}),
		},
		stdio: ["ignore", "pipe", "pipe"],
	});

	// Kept so a failure can say what the server actually complained about;
	// without it a crash on startup is indistinguishable from a slow one.
	let output = "";
	const record = (chunk: unknown) => {
		output = `${output}${chunk}`.slice(-4000);
	};

	child.stdout?.on("data", (chunk) => {
		record(chunk);
		process.stdout.write(`[api] ${chunk}`);
	});
	child.stderr?.on("data", (chunk) => {
		record(chunk);
		process.stderr.write(`[api] ${chunk}`);
	});

	// spawn reports a missing executable here rather than by throwing, so
	// without this listener the process simply never appears and the wait
	// below times out saying nothing about why
	const spawnFailure = new Promise<never>((_, reject) => {
		child.once("error", (error) =>
			reject(new Error(`could not start ${file}: ${error.message}`)),
		);
	});

	try {
		await Promise.race([
			waitUntilAnswering(baseUrl, token, child),
			spawnFailure,
		]);
	} catch (error) {
		stopChild(child);
		const detail = output.trim();
		throw new Error(
			detail
				? `${(error as Error).message}\n${detail}`
				: (error as Error).message,
		);
	}

	return { baseUrl, token, stop: () => stopChild(child) };
}

/**
 * Stop the API, and be sure about it.
 *
 * A surviving child is the worst failure this file has: it keeps the SQLite
 * file open and holds a port, so the next launch finds a database another
 * process is writing to. Windows does not kill a process tree when the parent
 * dies, hence taskkill; elsewhere SIGTERM is enough, with SIGKILL behind it
 * for a process that has stopped listening to polite requests.
 */
function stopChild(child: ChildProcess): void {
	if (child.exitCode !== null || child.signalCode !== null) {
		return;
	}

	if (process.platform === "win32" && child.pid !== undefined) {
		spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"]);
		return;
	}

	child.kill("SIGTERM");
	const forced = setTimeout(() => child.kill("SIGKILL"), 3_000);
	// nothing should be kept alive waiting to kill something already gone
	forced.unref?.();
	child.once("exit", () => clearTimeout(forced));
}
