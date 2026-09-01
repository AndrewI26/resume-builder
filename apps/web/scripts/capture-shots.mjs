/**
 * Regenerates the landing page's product screenshots into `public/shots`.
 *
 * The captures on the landing page are of the real app, so they go stale the
 * moment the UI moves. Re-run this rather than re-shooting by hand.
 *
 * Needs, none of which are project dependencies:
 *   bun add -d playwright      # drives Chrome
 *   brew install webp          # `cwebp`, to encode the output
 *
 * And a running stack, signed-in-able as the seeded demo account:
 *   bun run docker:dev  &&  bun run db:upgrade  &&  bun run db:seed
 *   bun run dev:api  &&  bun run dev:web
 *   (cd apps/api && uv run python worker.py)   # the PDF preview needs this
 *
 * Then:  bun run apps/web/scripts/capture-shots.mjs
 *
 * If a capture comes back with an error state in it — "the last compile
 * failed" in the editor preview, most often — the worker is down or holding a
 * dead database connection. Restart it and run this again; do not ship the
 * error.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:5173";
const EMAIL = process.env.DEMO_EMAIL ?? "demo@example.com";
const PASSWORD = process.env.DEMO_PASSWORD ?? "demo1234";

const here = dirname(fileURLToPath(import.meta.url));
const publicShots = join(here, "..", "public", "shots");
const staging = join(here, "..", ".shots-staging");

const VW = 1440;
const VH = 900;

// A phone, for the hero's small-screen variant. The editor genuinely reflows
// to a single column at this width, so that shot is a real capture rather than
// a crop of the desktop one — which, scaled into 390px, is illegible.
const MW = 390;
const MH = 780;

/** Sign in as the demo account, leaving the page on the dashboard. */
async function login(page) {
	await page.goto(`${BASE}/login`);
	await page.fill('input[type="email"]', EMAIL);
	await page.fill('input[type="password"]', PASSWORD);
	await page.click('button[type="submit"]');
	await page.waitForURL("**/dashboard");
}

/** Open the first resume in the editor and wait for the PDF to come back. */
async function openEditor(page) {
	await page.goto(`${BASE}/resumes`);
	await page.waitForSelector("tbody tr");
	const href = await page
		.locator("a[href^='/resumes/']")
		.first()
		.getAttribute("href");
	await page.goto(`${BASE}${href}`);
	await page.waitForSelector("h1");
	// the PDF is compiled on demand by the worker; give it room
	await page.waitForTimeout(9000);
}

/** Capture one theme's full set as PNGs into `outDir`. Returns their sizes. */
async function capture(theme, outDir) {
	const browser = await chromium.launch({ channel: "chrome" });
	const ctx = await browser.newContext({
		viewport: { width: VW, height: VH },
		deviceScaleFactor: 2,
		colorScheme: theme,
	});
	// pin the theme before app code runs, so nothing flashes the other palette
	await ctx.addInitScript((t) => {
		try {
			localStorage.setItem("theme", t);
		} catch {}
	}, theme);

	const page = await ctx.newPage();
	const dims = {};

	await login(page);

	/**
	 * Screenshot a padded box around `selector`, clamped to the viewport.
	 *
	 * The app centres its content in a wide column, so a plain viewport capture
	 * is mostly empty canvas — which reads as a tiny UI once the image sits in a
	 * half-width column on the landing page.
	 */
	const clipTo = async (name, selector, pad = 24, capHeight = VH) => {
		const box = await page.locator(selector).first().boundingBox();
		const x = Math.max(0, box.x - pad);
		const y = Math.max(0, box.y - pad);
		const width = Math.min(VW - x, box.width + pad * 2);
		const height = Math.min(VH - y, Math.min(box.height + pad * 2, capHeight));

		await page.screenshot({
			path: join(outDir, `${name}.png`),
			clip: { x, y, width, height },
		});
		dims[name] = { width: Math.round(width), height: Math.round(height) };
	};

	const full = async (name) => {
		await page.screenshot({ path: join(outDir, `${name}.png`) });
		dims[name] = { width: VW, height: VH };
	};

	// The editor is the hero, and its two-pane layout fills the frame already,
	// so it is the one shot taken whole rather than cropped.
	await openEditor(page);
	await full("editor");

	await page.goto(`${BASE}/sections`);
	await page.waitForSelector("tbody tr");
	await page.waitForTimeout(900);
	await clipTo("sections", "main", 24, 760);

	await page.goto(`${BASE}/resumes`);
	await page.waitForSelector("tbody tr");
	await page.waitForTimeout(900);
	await clipTo("resumes", "main", 24, 820);

	// the sections tables open their editor on row click rather than through a
	// link, so the populated form is only reachable by clicking the row
	await page.goto(`${BASE}/sections`);
	await page.waitForSelector("tbody tr");
	await page.getByText("Senior Software Engineer").first().click();
	await page.waitForSelector("form");
	await page.waitForTimeout(1200);
	await clipTo("section-form", "form", 24, 760);

	// enough dimmed page around the dialog for it to read as a modal
	await page.goto(`${BASE}/resumes`);
	await page.waitForSelector("tbody tr");
	await page.locator("button[aria-label^='Delete']").first().click();
	await page.waitForSelector("dialog[open]");
	await page.waitForTimeout(700);
	await clipTo("confirm", "dialog", 120, 620);

	await page.goto(`${BASE}/dashboard`);
	await page.waitForSelector("main");
	await page.waitForTimeout(900);
	await clipTo("dashboard", "main", 24, 620);

	await ctx.close();

	// ---- the hero's phone-width variant, in its own viewport ----------------
	const mobileCtx = await browser.newContext({
		viewport: { width: MW, height: MH },
		deviceScaleFactor: 2,
		colorScheme: theme,
	});
	await mobileCtx.addInitScript((t) => {
		try {
			localStorage.setItem("theme", t);
		} catch {}
	}, theme);

	const mobile = await mobileCtx.newPage();
	await login(mobile);
	await openEditor(mobile);

	// Frame the compiled document rather than the top of the stack: on a phone
	// the section list and the preview cannot both be in shot, and the preview
	// is the half that shows what the app is for.
	const preview = await mobile.locator("iframe, embed, object").first();

	// This has to be a viewport capture clipped after scrolling, not a
	// `fullPage` clip: Chrome's PDF plugin only paints while it is actually
	// on screen, and a full-page shot comes back with an empty rectangle where
	// the document should be.
	//
	// The preview sits at the end of the document, so scrolling it to the top
	// of the viewport clamps at the last screenful — hence measuring where
	// things actually landed rather than assuming.
	await mobile.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
	await mobile.waitForTimeout(1200);

	const settledPreview = await preview.boundingBox();
	const settledHeader = await mobile
		.getByText("Compiled from your saved resume.")
		.first()
		.boundingBox();

	const top = Math.max(0, (settledHeader?.y ?? settledPreview.y) - 20);
	const bottom = Math.min(MH, settledPreview.y + settledPreview.height + 16);

	await mobile.screenshot({
		path: join(outDir, "editor-mobile.png"),
		clip: { x: 0, y: top, width: MW, height: Math.ceil(bottom - top) },
	});
	dims["editor-mobile"] = { width: MW, height: Math.ceil(bottom - top) };

	await mobileCtx.close();
	await browser.close();

	return dims;
}

/** PNG → WebP. The captures are flat UI, so this is a big win for no visible cost. */
function encode(fromDir, toDir) {
	mkdirSync(toDir, { recursive: true });
	for (const file of readdirSync(fromDir).filter((f) => f.endsWith(".png"))) {
		const name = file.replace(/\.png$/, "");
		execFileSync("cwebp", [
			"-q",
			"84",
			"-m",
			"6",
			"-quiet",
			join(fromDir, file),
			"-o",
			join(toDir, `${name}.webp`),
		]);
	}
}

rmSync(staging, { recursive: true, force: true });

const sizes = {};
for (const theme of ["light", "dark"]) {
	const raw = join(staging, theme);
	mkdirSync(raw, { recursive: true });
	sizes[theme] = await capture(theme, raw);
	encode(raw, join(publicShots, theme));
	console.log(`captured ${theme}`);
}

rmSync(staging, { recursive: true, force: true });

// home.tsx states each shot's intrinsic size to hold layout while images load.
// Crops depend on content, so a data change can move them — if this disagrees
// with the SHOTS map there, update it.
console.log("\nintrinsic sizes (light):");
console.log(JSON.stringify(sizes.light, null, 2));

const mismatched = Object.keys(sizes.light).filter(
	(name) =>
		sizes.light[name].width !== sizes.dark[name].width ||
		sizes.light[name].height !== sizes.dark[name].height,
);
if (mismatched.length > 0) {
	console.warn(
		`\nlight and dark differ in size for: ${mismatched.join(", ")}.`,
		"\nOne size is used for both, so the odd one out will be letterboxed.",
	);
}
