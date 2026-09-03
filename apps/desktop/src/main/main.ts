/**
 * The desktop app: a window onto the same React app the browser gets, with the
 * API running beside it as a child process.
 *
 * The order matters here. The sidecar is started before the window is created,
 * so the renderer has an address to talk to by the time it asks for anything;
 * and it is stopped on the way out of every path that ends the app, because a
 * surviving child would hold the database open.
 */

import { app, BrowserWindow, shell } from "electron";
import { join } from "node:path";
import { APP_ORIGIN, registerAppScheme, serveAppFrom } from "./serve-app";
import { startSidecar, type Sidecar } from "./sidecar";

/** Set by electron-vite when the UI is being served by vite rather than built. */
const DEV_SERVER_URL = process.env.DESKTOP_UI_DEV_SERVER;

let sidecar: Sidecar | null = null;

// Before anything asks for a path: this names the folder the database lives
// in, under the user's application data directory, and "apps-desktop" is the
// package name rather than anything a person should have to recognise.
app.setName("Resume Builder");

registerAppScheme();

function createWindow(): BrowserWindow {
	const window = new BrowserWindow({
		width: 1280,
		height: 860,
		minWidth: 720,
		minHeight: 600,
		// the window is painted before the app has rendered anything, and an
		// empty white rectangle on a dark theme is worse than a moment's wait
		show: false,
		backgroundColor: "#0b0b0c",
		titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "default",
		webPreferences: {
			preload: join(__dirname, "../preload/preload.cjs"),
			// the renderer runs the same code the browser does, and is given
			// exactly what the preload script chooses to hand it
			contextIsolation: true,
			nodeIntegration: false,
			sandbox: true,
		},
	});

	window.once("ready-to-show", () => window.show());

	// a link to somewhere else is a link out of the application, not a request
	// to replace it — following one in place would leave no way back
	window.webContents.setWindowOpenHandler(({ url }) => {
		if (url.startsWith("http:") || url.startsWith("https:")) {
			void shell.openExternal(url);
		}
		return { action: "deny" };
	});

	return window;
}

async function start(): Promise<void> {
	sidecar = await startSidecar();

	// what the preload script passes to the renderer; it cannot be known until
	// the sidecar has picked a port, so it is set rather than compiled in
	process.env.RESUME_BUILDER_API_URL = sidecar.baseUrl;
	process.env.RESUME_BUILDER_API_TOKEN = sidecar.token;

	if (DEV_SERVER_URL === undefined) {
		serveAppFrom(join(__dirname, "../renderer"));
	}

	const window = createWindow();
	await window.loadURL(DEV_SERVER_URL ?? `${APP_ORIGIN}/`);
}

app.whenReady().then(async () => {
	try {
		await start();
	} catch (error) {
		// nothing works without the API, and a window showing failed requests
		// explains less than saying so plainly
		console.error("could not start the API:", error);
		app.quit();
	}

	app.on("activate", () => {
		if (BrowserWindow.getAllWindows().length === 0) {
			void createWindow().loadURL(DEV_SERVER_URL ?? `${APP_ORIGIN}/`);
		}
	});
});

app.on("window-all-closed", () => {
	if (process.platform !== "darwin") {
		app.quit();
	}
});

// Every path out of the app goes through here. 'will-quit' covers a normal
// quit and a signal; the process-level handlers cover the ones that do not
// reach the Electron event loop at all, and stopping twice is harmless.
app.on("will-quit", () => sidecar?.stop());
process.on("exit", () => sidecar?.stop());
process.on("SIGINT", () => app.quit());
process.on("SIGTERM", () => app.quit());
