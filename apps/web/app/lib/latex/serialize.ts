/**
 * `ResumeDocument` -> Jake's Resume LaTeX source.
 *
 * A pure function with no I/O, which is the point: where the resulting `.tex`
 * gets compiled — a WASM engine in the browser, or a TeX install on a server —
 * stays a swappable decision rather than an architectural one.
 */

import type {
	Education,
	Experience,
	PersonalInfo,
	Project,
	ResumeDocument,
	SectionBlock,
	Skill,
} from "../resume/types";
import { escapeLatex, escapeLatexUrl, renderBullet } from "./escape";
import { PREAMBLE } from "./preamble";

function href(url: string, body: string): string {
	return `\\href{${escapeLatexUrl(url)}}{${body}}`;
}

/**
 * Underline a contact label so the rule lands in the same place every time.
 *
 * `\underline` puts its rule below the *depth* of what it is given, and depth
 * depends on the characters present: `Portfolio` has no descenders and rides
 * high, while `github.com/...` has a `g`, a `j` and a `/` — all of which
 * descend in Computer Modern — and sits nearly 2pt lower. Left alone the
 * contact line underlines form a visible staircase.
 *
 * `\smash` drops the label's own height and depth, and the phantom then
 * imposes one fixed set taken from the deepest characters that show up in a
 * URL. The result no longer depends on what the text happens to spell.
 */
function underlined(label: string): string {
	return `\\underline{\\smash{${label}}\\vphantom{gj/}}`;
}

/** A contact line entry: an icon, then linked or plain text. */
function contact(icon: string, label: string, url?: string): string {
	const body = `\\raisebox{-0.2\\height}\\${icon}\\ ${underlined(label)}`;
	return url === undefined ? body : href(url, body);
}

/** Strip the scheme and any trailing slash, the way the template prints links. */
function displayUrl(url: string): string {
	return escapeLatex(url.replace(/^https?:\/\//, "").replace(/\/$/, ""));
}

function renderHeader(fullName: string, info: PersonalInfo | null): string {
	const entries: string[] = [];

	if (info?.phone_number) {
		entries.push(contact("faPhone", escapeLatex(info.phone_number)));
	}
	if (info?.email) {
		entries.push(
			contact("faEnvelope", escapeLatex(info.email), `mailto:${info.email}`),
		);
	}
	if (info?.linkedin) {
		entries.push(
			contact("faLinkedin", displayUrl(info.linkedin), info.linkedin),
		);
	}
	if (info?.github) {
		entries.push(contact("faGithub", displayUrl(info.github), info.github));
	}
	if (info?.portfolio) {
		entries.push(contact("faInternetExplorer", "Portfolio", info.portfolio));
	}
	if (info?.address) {
		entries.push(contact("faMapMarker", escapeLatex(info.address)));
	}

	return [
		"\\begin{center}",
		`    {\\Huge \\scshape ${escapeLatex(fullName)}} \\\\ \\vspace{1pt}`,
		...entries.map((entry) => `    ${entry} ~`),
		"\\end{center}",
	].join("\n");
}

function renderSkills(items: Skill[]): string {
	const lines = items.map(
		(skill) =>
			`     \\textbf{${escapeLatex(skill.name)}}{: ${escapeLatex(
				skill.items.join(", "),
			)} }`,
	);

	return [
		"\\section{Skills}",
		" \\begin{itemize}[leftmargin=0.15in, label={}]",
		"    \\small{\\item{",
		// the separator goes between lines, never after the last one
		`${lines.join(" \\\\\n")} }}`,
		" \\end{itemize}",
		" \\vspace{-20pt}",
	].join("\n");
}

function renderBullets(
	bullets: { text: string; bolded: [number, number][] }[],
) {
	if (bullets.length === 0) return [];

	return [
		"      \\resumeItemListStart",
		...bullets.map(
			(bullet) => `         \\resumeItem{${renderBullet(bullet)}}`,
		),
		"      \\resumeItemListEnd",
	];
}

function renderExperience(items: Experience[]): string {
	const entries = items.flatMap((experience) => [
		"    \\resumeSubheading",
		`        {\\textbf{${escapeLatex(experience.company)}}}{${escapeLatex(
			experience.duration,
		)}}`,
		`      {${escapeLatex(experience.position)}} {${escapeLatex(
			experience.location,
		)}}`,
		...renderBullets(experience.bullet_points),
		"",
	]);

	return [
		"\\section{Experience}",
		"  \\resumeSubHeadingListStart",
		...entries,
		"  \\resumeSubHeadingListEnd",
		"\\vspace{-16pt}",
	].join("\n");
}

function renderProjects(items: Project[]): string {
	const entries = items.flatMap((project, index) => {
		const name = `\\textbf{${escapeLatex(project.name)}}`;
		// a linked project gets a chain glyph in front of the name
		const title = project.link
			? `${href(project.link, "\\faLink")} ${name}`
			: name;
		const technologies = project.technologies.length
			? ` $|$ \\emph{ ${escapeLatex(project.technologies.join(", "))} }`
			: "";

		return [
			"      \\resumeProjectHeading",
			`          {${title}${technologies}}{}`,
			...renderBullets(project.bullet_points),
			// tightens the gap between entries, but not before the list ends
			...(index === items.length - 1 ? [] : ["          \\vspace{-16pt}", ""]),
		];
	});

	return [
		"\\section{Projects}",
		"    \\vspace{-5pt}",
		"    \\resumeSubHeadingListStart",
		...entries,
		"    \\resumeSubHeadingListEnd",
	].join("\n");
}

function renderEducation(items: Education[]): string {
	const entries = items.flatMap((education) => [
		"  \\resumeSubheading",
		`      {${escapeLatex(education.name)}}{${escapeLatex(education.duration)}}`,
		`      {${escapeLatex(education.subheading)}} {${escapeLatex(
			education.location,
		)}}`,
		"",
	]);

	return [
		"\\section{Education}",
		"  \\resumeSubHeadingListStart",
		...entries,
		"  \\resumeSubHeadingListEnd",
	].join("\n");
}

function renderBlock(block: SectionBlock): string {
	switch (block.type) {
		case "skill":
			return renderSkills(block.items);
		case "experience":
			return renderExperience(block.items);
		case "project":
			return renderProjects(block.items);
		case "education":
			return renderEducation(block.items);
	}
}

/** Build the complete `.tex` source for a resume document. */
export function serializeToTex(document: ResumeDocument): string {
	const body = document.sections
		// the API drops empty blocks, but a bare heading is ugly enough to
		// guard against twice
		.filter((block) => block.items.length > 0)
		.map(renderBlock);

	return [
		PREAMBLE,
		"",
		renderHeader(document.full_name, document.personal_info),
		"",
		...body.flatMap((section) => [section, ""]),
		"\\end{document}",
		"",
	].join("\n");
}
