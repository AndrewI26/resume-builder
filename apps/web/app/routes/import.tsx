import { $api } from "@api/api";
import type { components } from "@api/schema.d.ts";
import { Button } from "@components/button";
import { ExportLibraryButton } from "@components/export-library-button";
import { FormError } from "@components/section-form";
import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useRef, useState } from "react";
import { Link } from "react-router";
import { importProblems } from "~/lib/library/errors";
import { apiBaseUrl } from "~/platform/host";

type PortableLibrary = components["schemas"]["PortableLibrary"];
type ImportSummary = components["schemas"]["ImportSummary"];

export function meta() {
	return [{ title: "Import · Resume Builder" }];
}

const EXAMPLE = `{
  "format": "resume-builder",
  "version": 1,
  "personal_info": [
    {
      "key": "main",
      "email": "you@example.com",
      "phone_number": "+1 555 0100",
      "github": { "url": "https://github.com/you", "label": "you" }
    }
  ],
  "experience": [
    {
      "key": "acme",
      "company": "Acme",
      "position": "Software Engineer",
      "duration": "2024 - Present",
      "location": "Toronto, ON",
      "bullet_points": ["Built the thing", "Cut costs by 40%"]
    }
  ],
  "projects": [
    {
      "key": "whiz",
      "name": "Whiz",
      "github": "https://github.com/you/whiz",
      "technologies": ["Go"],
      "bullet_points": ["A small web framework"]
    }
  ],
  "skills": [
    { "key": "langs", "name": "Languages", "items": ["Python", "Go"] }
  ],
  "education": [],
  "resumes": [
    {
      "title": "Backend",
      "full_name": "Your Name",
      "personal_info": "main",
      "sections": {
        "experience": ["acme"],
        "project": ["whiz"],
        "skill": ["langs"]
      }
    }
  ]
}`;

const PROMPT = `Convert my resume into JSON for Resume Builder's import.

Rules:
- Output only the JSON, matching the JSON Schema below exactly. Do not add fields it doesn't define.
- Put each job in "experience", each project in "projects", each school in "education", and each group of skills in "skills". Contact details go in "personal_info".
- Give every entry a short unique "key", and add one resume to "resumes" that lists the keys of every entry under "sections".
- Bullet points are plain strings. Keep my wording.

JSON Schema:
`;

function summaryLine(summary: ImportSummary): string {
	const parts: [number, string, string][] = [
		[summary.resumes.length, "resume", "resumes"],
		[summary.experience, "experience", "experiences"],
		[summary.projects, "project", "projects"],
		[summary.education, "education entry", "education entries"],
		[summary.skills, "skill list", "skill lists"],
		[summary.personal_info, "contact block", "contact blocks"],
	];

	const counted = parts
		.filter(([count]) => count > 0)
		.map(([count, one, many]) => `${count} ${count === 1 ? one : many}`);

	return counted.length > 0 ? counted.join(", ") : "nothing";
}

function Panel({ children }: { children: ReactNode }) {
	return (
		<div className="mt-4 rounded-card border border-border bg-card-secondary px-6 py-5">
			{children}
		</div>
	);
}

export default function ImportRoute() {
	const queryClient = useQueryClient();
	const fileInput = useRef<HTMLInputElement>(null);

	const [text, setText] = useState("");
	const [problems, setProblems] = useState<string[]>([]);
	// the result of checking exactly the text currently in the box
	const [checked, setChecked] = useState<ImportSummary | null>(null);
	const [imported, setImported] = useState<ImportSummary | null>(null);
	const [notice, setNotice] = useState<string | null>(null);
	const [busy, setBusy] = useState(false);

	const { mutateAsync: importLibrary } = $api.useMutation(
		"post",
		"/library/import",
	);

	const edit = (value: string) => {
		setText(value);
		setChecked(null);
		setImported(null);
		setProblems([]);
	};

	const parsed = (): PortableLibrary | null => {
		try {
			return JSON.parse(text) as PortableLibrary;
		} catch (error) {
			setProblems([
				`That isn't valid JSON: ${error instanceof Error ? error.message : "it could not be read"}.`,
			]);
			return null;
		}
	};

	const run = async (dryRun: boolean) => {
		const body = parsed();
		if (body === null) {
			return;
		}

		setBusy(true);
		setProblems([]);
		try {
			const summary = await importLibrary({
				body,
				params: { query: { dry_run: dryRun } },
			});
			if (dryRun) {
				setChecked(summary);
			} else {
				setChecked(null);
				setImported(summary);
				setText("");
				await queryClient.invalidateQueries();
			}
		} catch (error) {
			setChecked(null);
			setProblems(importProblems(error));
		} finally {
			setBusy(false);
		}
	};

	const readFile = async (file: File | undefined) => {
		if (file !== undefined) {
			edit(await file.text());
		}
	};

	const copy = async (value: string, what: string) => {
		try {
			await navigator.clipboard.writeText(value);
			setNotice(`Copied the ${what}.`);
		} catch {
			setNotice(`Could not copy the ${what}.`);
		}
	};

	const copyPrompt = async () => {
		try {
			const schema = await fetch(`${apiBaseUrl}/library/schema`).then(
				(response) => response.json(),
			);
			await copy(`${PROMPT}${JSON.stringify(schema, null, 2)}`, "AI prompt");
		} catch {
			setNotice("Could not load the schema. Try again.");
		}
	};

	return (
		<main className="mx-auto w-full max-w-3xl px-4 py-16">
			<Link
				className="inline-flex items-center gap-1 text-ink-subtle text-sm transition-colors hover:text-ink"
				to="/sections"
			>
				<svg
					aria-hidden="true"
					fill="none"
					height="16"
					stroke="currentColor"
					strokeLinecap="round"
					strokeLinejoin="round"
					strokeWidth="2"
					viewBox="0 0 24 24"
					width="16"
				>
					<path d="M19 12H5M12 19l-7-7 7-7" />
				</svg>
				<span className="text-trim">Back to sections</span>
			</Link>

			<h1 className="mt-4 text-4xl leading-heading tracking-decreased">
				Import
			</h1>
			<p className="mt-2 text-ink-subtle leading-body">
				Add sections and resumes from a JSON file. Nothing you already have is
				changed, and if anything in the file is wrong, nothing is added.
			</p>

			<section className="mt-8 flex flex-col gap-4">
				<div className="flex flex-wrap items-center justify-between gap-2">
					<label className="text-ink-subtle text-sm" htmlFor="import-json">
						Paste JSON, or choose a file
					</label>
					<Button onClick={() => fileInput.current?.click()} variant="tertiary">
						Choose file
					</Button>
					<input
						accept="application/json,.json"
						className="hidden"
						onChange={(event) => {
							readFile(event.target.files?.[0]);
							event.target.value = "";
						}}
						ref={fileInput}
						type="file"
					/>
				</div>

				<textarea
					className="h-72 w-full resize-y rounded-xl border border-border bg-field px-4 py-3 font-mono text-ink text-sm outline-none transition-colors placeholder:text-ink-disabled focus:border-stroke"
					id="import-json"
					onChange={(event) => edit(event.target.value)}
					placeholder={
						'{\n  "format": "resume-builder",\n  "version": 1,\n  …\n}'
					}
					spellCheck={false}
					value={text}
				/>

				{problems.length === 1 && <FormError>{problems[0]}</FormError>}
				{problems.length > 1 && (
					// a list can't sit inside FormError's paragraph, so this is
					// the same look on a div
					<div
						className="rounded-xl bg-negative-bg px-4 py-2 text-negative text-sm"
						role="alert"
					>
						The file has {problems.length} problems:
						<ul className="mt-1 list-disc pl-5">
							{problems.map((problem) => (
								<li key={problem}>{problem}</li>
							))}
						</ul>
					</div>
				)}

				{checked !== null && (
					<p className="rounded-xl bg-field px-4 py-2 text-ink text-sm">
						Ready to import {summaryLine(checked)}.
					</p>
				)}

				{imported !== null && (
					<div className="rounded-xl bg-field px-4 py-3 text-ink text-sm">
						Imported {summaryLine(imported)}.
						{imported.resumes.length > 0 && (
							<ul className="mt-1 list-disc pl-5">
								{imported.resumes.map((resume) => (
									<li key={resume.id}>
										<Link
											className="underline underline-offset-4"
											to={`/resumes/${resume.id}`}
										>
											{resume.title}
										</Link>
									</li>
								))}
							</ul>
						)}
					</div>
				)}

				<div className="flex flex-wrap justify-end gap-2">
					<Button
						disabled={busy || text.trim() === ""}
						onClick={() => run(true)}
						variant="secondary"
					>
						{busy && checked === null ? "Checking…" : "Check"}
					</Button>
					<Button
						disabled={busy || checked === null}
						onClick={() => run(false)}
					>
						{busy && checked !== null ? "Importing…" : "Import"}
					</Button>
				</div>
			</section>

			<section className="mt-12">
				<h2 className="text-2xl leading-heading tracking-decreased">
					The format
				</h2>
				<p className="mt-2 text-ink-subtle leading-body">
					One JSON object with lists of sections and resumes. Every list is
					optional. A resume refers to its sections by the{" "}
					<code className="font-mono text-sm">key</code> you give them.
				</p>

				<Panel>
					<pre className="max-h-80 overflow-auto font-mono text-ink text-xs leading-relaxed">
						{EXAMPLE}
					</pre>
				</Panel>

				<div className="mt-4 flex flex-wrap gap-2">
					<Button onClick={() => copy(EXAMPLE, "example")} variant="secondary">
						Copy example
					</Button>
					<Button onClick={copyPrompt} variant="secondary">
						Copy AI prompt
					</Button>
					<a
						className="inline-flex h-10 items-center rounded-button px-4 text-ink-subtle transition-colors hover:text-ink"
						href={`${apiBaseUrl}/library/schema`}
						rel="noreferrer"
						target="_blank"
					>
						<span className="text-trim">View JSON Schema</span>
					</a>
				</div>
				<p className="mt-3 text-ink-subtle text-sm leading-body">
					To use an AI tool, copy the prompt, paste it into the tool with your
					resume, then paste its answer above.
				</p>

				{notice !== null && (
					<p className="mt-3 text-ink-subtle text-sm" role="status">
						{notice}
					</p>
				)}
			</section>

			<section className="mt-12">
				<h2 className="text-2xl leading-heading tracking-decreased">Export</h2>
				<p className="mt-2 text-ink-subtle leading-body">
					Download everything you have in the same format, to back it up or edit
					it and import it again. Importing it again adds copies.
				</p>
				<div className="mt-4">
					<ExportLibraryButton />
				</div>
			</section>
		</main>
	);
}
