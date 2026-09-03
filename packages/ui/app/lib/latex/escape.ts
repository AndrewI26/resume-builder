/**
 * Turning user text into LaTeX source.
 *
 * Every string that reaches the template goes through here first. Missing an
 * escape does not merely look wrong — a stray `\` or `%` in a name silently
 * changes what the rest of the document means, or fails the compile outright.
 */

import { splitBullet } from "../resume/bullet";
import type { BulletPoint } from "../resume/types";

const ESCAPES: Record<string, string> = {
	"\\": "\\textbackslash{}",
	"{": "\\{",
	"}": "\\}",
	$: "\\$",
	"&": "\\&",
	"#": "\\#",
	_: "\\_",
	"%": "\\%",
	"~": "\\textasciitilde{}",
	"^": "\\textasciicircum{}",
};

/**
 * Escape the ten characters LaTeX treats specially.
 *
 * Done in a single pass on purpose: escaping `\` first would produce a
 * `\textbackslash{}` whose own braces a later pass would then escape again.
 */
export function escapeLatex(value: string): string {
	return value.replace(/[\\{}$&#_%~^]/g, (character) => ESCAPES[character]);
}

const URL_ENCODES: Record<string, string> = {
	"\\": "%5C",
	"{": "%7B",
	"}": "%7D",
	$: "%24",
	"&": "%26",
	"#": "%23",
	_: "%5F",
	"^": "%5E",
	"~": "%7E",
	"%": "%25",
};

/**
 * Make a URL safe as the target of `\href`.
 *
 * Backslash escaping is not an option here. Jake's template calls `\href`
 * from inside other macros' arguments, where hyperref cannot apply its
 * verbatim catcodes, so `~` would expand to a non-breaking space and change
 * the address. Percent-encoding sidesteps the catcodes entirely and means the
 * same thing to a browser.
 *
 * A `%` that already introduces a valid escape sequence is left alone, so a
 * pre-encoded URL survives the trip rather than becoming `%2520`.
 */
export function escapeLatexUrl(url: string): string {
	return url.replace(
		/[\\{}$&#_^~]|%(?![0-9A-Fa-f]{2})/g,
		(character) => URL_ENCODES[character],
	);
}

/**
 * Render one bullet point, wrapping its bolded ranges in `\textbf`.
 *
 * Each segment is escaped on its own and only then wrapped. Escaping the whole
 * string up front would shift every offset — a name containing `&` becomes two
 * characters longer — and the bolding would land in the wrong place.
 */
export function renderBullet(bullet: BulletPoint): string {
	return splitBullet(bullet)
		.map((segment) =>
			segment.bold
				? `\\textbf{${escapeLatex(segment.text)}}`
				: escapeLatex(segment.text),
		)
		.join("");
}
