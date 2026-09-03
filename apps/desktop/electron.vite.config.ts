import { resolve } from "node:path";
import { defineConfig } from "electron-vite";

/**
 * Only the main process and the preload script are built here.
 *
 * The renderer is the app in packages/ui, built by React Router — the same
 * bundle the browser deployment serves. Building it a second way would be a
 * second chance for the two to differ.
 */
export default defineConfig({
	// .cjs rather than .js: the package is type: module, so a .js file would be
	// loaded as ESM and the CommonJS bundle rollup emits would not run.
	main: {
		build: {
			outDir: "dist/main",
			lib: { entry: resolve(__dirname, "src/main/main.ts") },
			rollupOptions: {
				// electron is provided by the runtime, not bundled: the npm
				// package is only a shim that reports where the binary is, and
				// inlining it makes the main process import that instead of the
				// real API
				external: ["electron"],
				output: { format: "cjs", entryFileNames: "main.cjs" },
			},
		},
	},
	preload: {
		build: {
			outDir: "dist/preload",
			lib: { entry: resolve(__dirname, "src/preload/preload.ts") },
			rollupOptions: {
				external: ["electron"],
				output: { format: "cjs", entryFileNames: "preload.cjs" },
			},
		},
	},
});
