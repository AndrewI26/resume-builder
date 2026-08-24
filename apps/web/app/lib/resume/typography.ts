/**
 * The text substitutions TeX makes on its way to the page.
 *
 * Only the preview needs these. The LaTeX path must *not* apply them — it
 * passes the raw text through and lets TeX do its own thing — so running them
 * there would double up. Keeping them out of `escape.ts` is deliberate.
 */

/**
 * Apply TeX's dash ligatures: `--` becomes an en dash, `---` an em dash.
 *
 * Without this a duration typed as `May 2025 -- August 2025` reads as two
 * hyphens in the preview and a proper en dash in the PDF, which makes the
 * preview look wrong for something the user did correctly.
 */
export function typeset(text: string): string {
	return text.replace(/---/g, "—").replace(/(?<!-)--(?!-)/g, "–");
}
