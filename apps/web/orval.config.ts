import { readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { defineConfig } from "orval";

const apiUrl = process.env.VITE_API_URL ?? "http://localhost:8000";
const generated = "./app/api/generated";
const banner = "// @ts-nocheck\n";

const skipTypechecking = async (dir: string): Promise<void> => {
	for (const entry of await readdir(dir, { withFileTypes: true })) {
		const path = join(dir, entry.name);

		if (entry.isDirectory()) {
			await skipTypechecking(path);
			continue;
		}
		if (!entry.name.endsWith(".ts")) continue;

		const source = await readFile(path, "utf8");
		if (source.startsWith(banner)) continue;

		await writeFile(path, banner + source);
	}
};

export default defineConfig({
	api: {
		input: {
			target: `${apiUrl}/openapi.json`,
		},
		output: {
			mode: "tags-split",
			target: `${generated}/endpoints`,
			schemas: `${generated}/model`,
			client: "react-query",
			httpClient: "fetch",
			clean: true,
			indexFiles: true,
			override: {
				mutator: {
					path: "./app/api/fetcher.ts",
					name: "fetcher",
				},
			},
		},
		hooks: {
			afterAllFilesWrite: () => skipTypechecking(generated),
		},
	},
});
