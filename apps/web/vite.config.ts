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
		},
	};
});
