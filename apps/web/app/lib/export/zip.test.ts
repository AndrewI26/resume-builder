import { describe, expect, test } from "bun:test";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { crc32, zip } from "./zip";

const encode = (text: string) => new TextEncoder().encode(text);

describe("crc32", () => {
	test("matches the standard check value", () => {
		expect(crc32(encode("123456789"))).toBe(0xcbf43926);
	});
});

describe("zip", () => {
	// the real test of a ZIP writer is whether a real unzip accepts it
	test("produces an archive unzip extracts byte for byte", async () => {
		const folder = mkdtempSync(join(tmpdir(), "zip-test-"));
		try {
			const archive = join(folder, "out.zip");
			writeFileSync(
				archive,
				new Uint8Array(
					await zip([
						{ name: "backend.pdf", data: encode("%PDF-1.5 backend") },
						{ name: "frontend-2.pdf", data: encode("%PDF-1.5 frontend") },
					]).arrayBuffer(),
				),
			);

			expect(Bun.spawnSync(["unzip", "-tq", archive]).exitCode).toBe(0);

			Bun.spawnSync(["unzip", "-q", archive, "-d", join(folder, "out")]);
			expect(readFileSync(join(folder, "out", "backend.pdf"), "utf8")).toBe(
				"%PDF-1.5 backend",
			);
			expect(readFileSync(join(folder, "out", "frontend-2.pdf"), "utf8")).toBe(
				"%PDF-1.5 frontend",
			);
		} finally {
			rmSync(folder, { recursive: true, force: true });
		}
	});

	// macOS's bundled unzip ignores the UTF-8 flag (Finder and current tools
	// honour it), so accented names are checked in the bytes themselves
	test("marks names as UTF-8 and stores them that way", async () => {
		const bytes = new Uint8Array(
			await zip([{ name: "café.pdf", data: encode("x") }]).arrayBuffer(),
		);
		const view = new DataView(bytes.buffer);

		expect(view.getUint16(6, true) & 0x0800).toBe(0x0800);
		const nameLength = view.getUint16(26, true);
		expect(new TextDecoder().decode(bytes.slice(30, 30 + nameLength))).toBe(
			"café.pdf",
		);
	});

	test("an empty archive is still valid", async () => {
		expect((await zip([]).arrayBuffer()).byteLength).toBe(22);
	});
});
