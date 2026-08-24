import { describe, expect, test } from "bun:test";
import type { PersonalInfo, ResumeDocument } from "../resume/types";
import { SAMPLE_DOCUMENT } from "./__fixtures__/sample-document";
import { PREAMBLE } from "./preamble";
import { serializeToTex } from "./serialize";

const expectedTex = await Bun.file(
	new URL("./__fixtures__/expected.tex", import.meta.url),
).text();

/** How a contact label is expected to appear once underlined. */
const underlined = (label: string) =>
	`\\underline{\\smash{${label}}\\vphantom{gj/}}`;

const emptyInfo: PersonalInfo = {
	id: "50000000-0000-0000-0000-0000000000ff",
	email: null,
	phone_number: null,
	address: null,
	github: null,
	linkedin: null,
	portfolio: null,
};

/**
 * Just the generated part.
 *
 * The preamble defines the very macros the body calls, so a bare `toContain`
 * over the whole document would match `\\newcommand{\\resumeItemListStart}`
 * and quietly pass regardless of what was generated.
 */
function body(tex: string): string {
	return tex.slice(PREAMBLE.length);
}

function document(overrides: Partial<ResumeDocument> = {}): ResumeDocument {
	return {
		id: "00000000-0000-0000-0000-000000000001",
		title: "Untitled",
		template: "jakes",
		full_name: "Ada Lovelace",
		personal_info: null,
		sections: [],
		...overrides,
	};
}

describe("golden file", () => {
	test("reproduces the checked-in expected output", () => {
		expect(serializeToTex(SAMPLE_DOCUMENT)).toBe(expectedTex);
	});
});

describe("document structure", () => {
	test("opens with the frozen preamble", () => {
		expect(serializeToTex(document()).startsWith(PREAMBLE)).toBe(true);
	});

	test("closes the document", () => {
		expect(
			serializeToTex(document()).trimEnd().endsWith("\\end{document}"),
		).toBe(true);
	});

	test("emits a usable document even with no sections at all", () => {
		const tex = serializeToTex(document());

		expect(tex).toContain("\\begin{center}");
		expect(tex).toContain("\\end{document}");
		expect(body(tex)).not.toContain("\\section{");
	});

	test("orders sections as the document lists them", () => {
		const tex = serializeToTex(
			document({
				sections: [
					{
						type: "education",
						items: SAMPLE_DOCUMENT.sections[3].items as never,
					},
					{ type: "skill", items: SAMPLE_DOCUMENT.sections[0].items as never },
				],
			}),
		);

		expect(tex.indexOf("\\section{Education}")).toBeLessThan(
			tex.indexOf("\\section{Skills}"),
		);
	});

	test("omits a block whose items are empty", () => {
		const tex = serializeToTex(
			document({ sections: [{ type: "skill", items: [] }] }),
		);

		expect(tex).not.toContain("\\section{Skills}");
	});
});

describe("header", () => {
	test("prints the full name", () => {
		expect(serializeToTex(document({ full_name: "Ada Lovelace" }))).toContain(
			"{\\Huge \\scshape Ada Lovelace}",
		);
	});

	test("escapes the full name", () => {
		expect(serializeToTex(document({ full_name: "A & B" }))).toContain(
			"{\\Huge \\scshape A \\& B}",
		);
	});

	test("renders a header with no contact details at all", () => {
		const tex = serializeToTex(document({ personal_info: null }));

		expect(tex).toContain("\\begin{center}");
		expect(tex).not.toContain("\\faEnvelope");
	});

	test("omits every field that is null", () => {
		const tex = serializeToTex(document({ personal_info: emptyInfo }));

		for (const icon of ["faEnvelope", "faGithub", "faLinkedin", "faPhone"]) {
			expect(tex).not.toContain(icon);
		}
	});

	test("links an email as a mailto", () => {
		const tex = serializeToTex(
			document({ personal_info: { ...emptyInfo, email: "ada@example.com" } }),
		);

		expect(tex).toContain("\\href{mailto:ada@example.com}");
		expect(tex).toContain(`\\faEnvelope\\ ${underlined("ada@example.com")}`);
	});

	test("prints a phone number without a link", () => {
		const tex = serializeToTex(
			document({
				personal_info: { ...emptyInfo, phone_number: "+1 555 0100" },
			}),
		);

		expect(tex).toContain(`\\faPhone\\ ${underlined("+1 555 0100")}`);
		expect(tex).not.toContain("\\href{+1 555 0100}");
	});

	test("strips the scheme from a displayed link", () => {
		const tex = serializeToTex(
			document({
				personal_info: { ...emptyInfo, github: "https://github.com/ada" },
			}),
		);

		expect(tex).toContain(underlined("github.com/ada"));
		expect(tex).toContain("\\href{https://github.com/ada}");
	});

	test("strips a trailing slash from a displayed link", () => {
		const tex = serializeToTex(
			document({
				personal_info: {
					...emptyInfo,
					linkedin: "https://linkedin.com/in/ada/",
				},
			}),
		);

		expect(tex).toContain(underlined("linkedin.com/in/ada"));
	});

	test("gives every underline the same depth, whatever the text spells", () => {
		// `Portfolio` has no descenders and `github.com/x` has three; without
		// the phantom their rules land at different heights
		const tex = serializeToTex(
			document({
				personal_info: {
					...emptyInfo,
					portfolio: "https://ada.dev",
					github: "https://github.com/ada",
				},
			}),
		);

		expect(tex).toContain(underlined("Portfolio"));
		expect(tex).toContain(underlined("github.com/ada"));
	});

	test("labels a portfolio rather than printing its URL", () => {
		const tex = serializeToTex(
			document({
				personal_info: { ...emptyInfo, portfolio: "https://ada.dev" },
			}),
		);

		expect(tex).toContain(underlined("Portfolio"));
	});
});

describe("skills", () => {
	test("joins items with commas", () => {
		const tex = serializeToTex(
			document({
				sections: [
					{
						type: "skill",
						items: [
							{ id: "1", name: "Languages", items: ["Go", "SQL"], position: 0 },
						],
					},
				],
			}),
		);

		expect(tex).toContain("\\textbf{Languages}{: Go, SQL }");
	});

	test("separates lists but does not trail the separator", () => {
		const tex = serializeToTex(
			document({
				sections: [
					{
						type: "skill",
						items: [
							{ id: "1", name: "A", items: ["x"], position: 0 },
							{ id: "2", name: "B", items: ["y"], position: 1 },
						],
					},
				],
			}),
		);

		// exactly one `\\` separator, between the two lines
		expect(tex.match(/\{: x \} \\\\/g)).toHaveLength(1);
		expect(tex).toContain("\\textbf{B}{: y } }}");
	});
});

describe("projects", () => {
	const project = (overrides = {}) => ({
		id: "1",
		name: "Whiz",
		link: null as string | null,
		technologies: ["Go"],
		bullet_points: [],
		...overrides,
	});

	test("prefixes a linked project with a chain glyph", () => {
		const tex = serializeToTex(
			document({
				sections: [
					{
						type: "project",
						items: [project({ link: "https://example.com/whiz" })],
					},
				],
			}),
		);

		expect(tex).toContain(
			"{\\href{https://example.com/whiz}{\\faLink} \\textbf{Whiz}",
		);
	});

	test("omits the glyph when there is no link", () => {
		const tex = serializeToTex(
			document({ sections: [{ type: "project", items: [project()] }] }),
		);

		expect(body(tex)).not.toContain("\\faLink");
		expect(tex).toContain("{\\textbf{Whiz} $|$");
	});

	test("omits the technologies clause when the list is empty", () => {
		const tex = serializeToTex(
			document({
				sections: [{ type: "project", items: [project({ technologies: [] })] }],
			}),
		);

		expect(tex).toContain("{\\textbf{Whiz}}{}");
		expect(body(tex)).not.toContain("$|$");
	});

	test("omits the bullet list when a project has no bullets", () => {
		const tex = serializeToTex(
			document({ sections: [{ type: "project", items: [project()] }] }),
		);

		expect(body(tex)).not.toContain("\\resumeItemListStart");
	});

	test("tightens between entries but not after the last", () => {
		const tex = serializeToTex(
			document({
				sections: [
					{
						type: "project",
						items: [project({ id: "1" }), project({ id: "2" })],
					},
				],
			}),
		);

		expect(tex.match(/\\vspace\{-16pt\}/g)).toHaveLength(1);
	});
});

describe("experience", () => {
	test("lays out the four-part subheading", () => {
		const tex = serializeToTex(
			document({
				sections: [
					{
						type: "experience",
						items: [
							{
								id: "1",
								company: "Acme",
								position: "Engineer",
								duration: "2020 - 2022",
								location: "Boston, MA",
								bullet_points: [],
							},
						],
					},
				],
			}),
		);

		expect(tex).toContain("{\\textbf{Acme}}{2020 - 2022}");
		expect(tex).toContain("{Engineer} {Boston, MA}");
	});

	test("escapes every part of the subheading", () => {
		const tex = serializeToTex(
			document({
				sections: [
					{
						type: "experience",
						items: [
							{
								id: "1",
								company: "R&D Inc",
								position: "100% Remote",
								duration: "2020 - 2022",
								location: "A_B",
								bullet_points: [],
							},
						],
					},
				],
			}),
		);

		expect(tex).toContain("{\\textbf{R\\&D Inc}}");
		expect(tex).toContain("{100\\% Remote} {A\\_B}");
	});
});
