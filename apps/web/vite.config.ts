import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
	const envDir = "../..";
	// loadEnv's default prefix filter only exposes VITE_-prefixed vars; pass ""
	// to also read FRONTEND_PORT for the dev server's own port below.
	const env = loadEnv(mode, envDir, "");

	return {
		envDir,
		plugins: [tailwindcss(), reactRouter()],
		resolve: {
			tsconfigPaths: true,
		},
		server: {
			port: Number(env.FRONTEND_PORT) || 5173,
			strictPort: true,
			// Safari caches dev-served JS more aggressively than Chrome and can
			// keep serving a stale route manifest after routes.ts changes even
			// on reload; force every dev response to be revalidated.
			headers:
				env.NODE_ENV === "development"
					? { "Cache-Control": "no-store" }
					: undefined,
		},
	};
});
