import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
	const envDir = "../../";
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
			headers:
				env.NODE_ENV === "development"
					? { "Cache-Control": "no-store" }
					: undefined,
		},
	};
});
