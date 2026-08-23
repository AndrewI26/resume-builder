import { $api } from "@api/api";
import type { components } from "@api/schema.d.ts";
import { Button } from "@components/button";
import { Table } from "@components/table";
import { useForm } from "@tanstack/react-form";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router";

export function meta() {
	return [{ title: "Resumes · Resume Builder" }];
}

type Resume = components["schemas"]["ResumeRead"];
type CreateResumeError =
	| components["schemas"]["ErrorDetail"]
	| components["schemas"]["HTTPValidationError"];

function createResumeErrorMessage(error: unknown): string {
	const detail = (error as CreateResumeError | undefined)?.detail;

	if (typeof detail === "string") {
		return detail;
	}

	if (Array.isArray(detail) && detail.length > 0) {
		return detail.map((item) => item.msg).join(" ");
	}

	return "Could not create the resume. Please try again.";
}

const dateFormatter = new Intl.DateTimeFormat("en-US", { dateStyle: "medium" });

const SECTION_TYPES = [
	{ value: "education", label: "Education" },
	{ value: "experience", label: "Experience" },
	{ value: "personal_info", label: "Personal info" },
	{ value: "project", label: "Project" },
	{ value: "skill", label: "Skill" },
] as const;

type SectionType = (typeof SECTION_TYPES)[number]["value"];

type SectionOption = { id: string; label: string };

const selectClassName =
	"w-full rounded-xl border border-border bg-field px-4 py-2 text-ink text-trim outline-none transition-colors focus:border-stroke disabled:text-ink-disabled";

/** Fetches the pickable items for one section type and reduces them to id/label options.
 *
 * Each section type lives behind a differently-shaped endpoint, so every case here
 * queries its own path; `enabled` keeps the inactive ones from firing.
 */
function useSectionOptions(sectionType: SectionType | ""): {
	options: SectionOption[];
	isLoading: boolean;
} {
	const education = $api.useQuery("get", "/education/", undefined, {
		enabled: sectionType === "education",
	});
	const experience = $api.useQuery("get", "/experience/", undefined, {
		enabled: sectionType === "experience",
	});
	const personalInfo = $api.useQuery("get", "/personal-info/", undefined, {
		enabled: sectionType === "personal_info",
	});
	const project = $api.useQuery("get", "/project/", undefined, {
		enabled: sectionType === "project",
	});
	const skill = $api.useQuery("get", "/skill/", undefined, {
		enabled: sectionType === "skill",
	});

	return useMemo(() => {
		switch (sectionType) {
			case "education":
				return {
					options: (education.data ?? []).map((row) => ({
						id: row.id,
						label: row.name,
					})),
					isLoading: education.isPending,
				};
			case "experience":
				return {
					options: (experience.data ?? []).map((row) => ({
						id: row.id,
						label: `${row.position} at ${row.company}`,
					})),
					isLoading: experience.isPending,
				};
			case "personal_info":
				return {
					options: (personalInfo.data ?? []).map((row) => ({
						id: row.id,
						label: row.email ?? row.address ?? "Personal info",
					})),
					isLoading: personalInfo.isPending,
				};
			case "project":
				return {
					options: (project.data ?? []).map((row) => ({
						id: row.id,
						label: row.name,
					})),
					isLoading: project.isPending,
				};
			case "skill":
				return {
					options: (skill.data ?? []).map((row) => ({
						id: row.id,
						label: row.name,
					})),
					isLoading: skill.isPending,
				};
			default:
				return { options: [], isLoading: false };
		}
	}, [
		sectionType,
		education.data,
		education.isPending,
		experience.data,
		experience.isPending,
		personalInfo.data,
		personalInfo.isPending,
		project.data,
		project.isPending,
		skill.data,
		skill.isPending,
	]);
}

function SectionPicker({
	sections,
	onAdd,
	onRemove,
	onMove,
}: {
	sections: (SectionOption & { type: SectionType })[];
	onAdd: (section: SectionOption & { type: SectionType }) => void;
	onRemove: (sectionId: string) => void;
	onMove: (sectionId: string, direction: "up" | "down") => void;
}) {
	const [sectionType, setSectionType] = useState<SectionType | "">("");
	const [sectionId, setSectionId] = useState("");
	const { options, isLoading } = useSectionOptions(sectionType);

	const addedIds = new Set(sections.map((section) => section.id));
	const availableOptions = options.filter((option) => !addedIds.has(option.id));

	return (
		<div className="mt-6 rounded-xl border border-border p-4">
			<p className="text-ink-subtle text-sm">Sections</p>

			<div className="mt-2 flex items-end gap-3">
				<div className="flex flex-1 flex-col gap-1">
					<label className="text-ink-subtle text-sm" htmlFor="section-type">
						Section type
					</label>
					<select
						className={selectClassName}
						id="section-type"
						onChange={(event) => {
							setSectionType(event.target.value as SectionType | "");
							setSectionId("");
						}}
						value={sectionType}
					>
						<option value="">Choose a type…</option>
						{SECTION_TYPES.map((type) => (
							<option key={type.value} value={type.value}>
								{type.label}
							</option>
						))}
					</select>
				</div>

				<div className="flex flex-1 flex-col gap-1">
					<label className="text-ink-subtle text-sm" htmlFor="section-item">
						Section
					</label>
					<select
						className={selectClassName}
						disabled={sectionType === ""}
						id="section-item"
						onChange={(event) => setSectionId(event.target.value)}
						value={sectionId}
					>
						<option value="">
							{isLoading ? "Loading…" : "Choose a section…"}
						</option>
						{availableOptions.map((option) => (
							<option key={option.id} value={option.id}>
								{option.label}
							</option>
						))}
					</select>
				</div>

				<Button
					disabled={sectionType === "" || sectionId === ""}
					onClick={() => {
						if (sectionType === "") {
							return;
						}
						const option = options.find((item) => item.id === sectionId);
						if (option === undefined) {
							return;
						}
						onAdd({ ...option, type: sectionType });
						setSectionId("");
					}}
					variant="secondary"
					type="button"
				>
					Add
				</Button>
			</div>

			{sections.length > 0 && (
				<ol className="mt-4 flex flex-col gap-2">
					{sections.map((section, index) => (
						<li
							className="flex items-center justify-between gap-3 rounded-lg bg-field px-3 py-2 text-sm"
							key={section.id}
						>
							<span>
								{index + 1}.{" "}
								{SECTION_TYPES.find((type) => type.value === section.type)
									?.label ?? section.type}{" "}
								— {section.label}
							</span>
							<span className="flex shrink-0 items-center gap-3">
								<button
									aria-label="Move up"
									className="text-ink-subtle enabled:hover:text-ink disabled:opacity-30"
									disabled={index === 0}
									onClick={() => onMove(section.id, "up")}
									type="button"
								>
									↑
								</button>
								<button
									aria-label="Move down"
									className="text-ink-subtle enabled:hover:text-ink disabled:opacity-30"
									disabled={index === sections.length - 1}
									onClick={() => onMove(section.id, "down")}
									type="button"
								>
									↓
								</button>
								<button
									aria-label="Remove"
									className="text-ink-subtle hover:text-negative"
									onClick={() => onRemove(section.id)}
									type="button"
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
										<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6" />
										<path d="M10 11v6M14 11v6" />
									</svg>
								</button>
							</span>
						</li>
					))}
				</ol>
			)}
		</div>
	);
}

function CreateResumeForm() {
	const queryClient = useQueryClient();
	const [formError, setFormError] = useState<string | null>(null);
	const [sections, setSections] = useState<
		(SectionOption & { type: SectionType })[]
	>([]);
	const { mutateAsync: createResume } = $api.useMutation("post", "/resumes/");

	const form = useForm({
		defaultValues: { name: "" },
		onSubmit: async ({ value, formApi }) => {
			setFormError(null);
			try {
				await createResume({
					body: {
						name: value.name,
						sections: sections.map((section) => section.id),
					},
				});
				await queryClient.invalidateQueries({
					queryKey: $api.queryOptions("get", "/resumes/").queryKey,
				});
				formApi.reset();
				setSections([]);
			} catch (error) {
				setFormError(createResumeErrorMessage(error));
			}
		},
	});

	return (
		<form
			className="mt-8"
			method="post"
			noValidate
			onSubmit={(event) => {
				event.preventDefault();
				form.handleSubmit();
			}}
		>
			<div className="flex items-start gap-3">
				<form.Field
					name="name"
					validators={{
						onSubmit: ({ value }) =>
							value.trim().length > 0 ? undefined : "Enter a resume name.",
					}}
				>
					{(field) => (
						<div className="flex flex-1 flex-col gap-1">
							<label className="sr-only" htmlFor={field.name}>
								Resume name
							</label>
							<input
								aria-invalid={field.state.meta.errors.length > 0}
								className="w-full rounded-xl border border-border bg-field px-4 py-2 text-ink text-trim outline-none transition-colors placeholder:text-ink-disabled focus:border-stroke aria-invalid:border-negative"
								id={field.name}
								name={field.name}
								onChange={(event) => field.handleChange(event.target.value)}
								placeholder="e.g. Frontend Focused"
								value={field.state.value}
							/>
							{field.state.meta.errors[0] && (
								<p className="text-negative text-sm">
									{field.state.meta.errors[0]}
								</p>
							)}
						</div>
					)}
				</form.Field>

				<form.Subscribe
					selector={(state) => [state.canSubmit, state.isSubmitting] as const}
				>
					{([canSubmit, isSubmitting]) => (
						<Button disabled={!canSubmit} type="submit">
							{isSubmitting ? "Creating…" : "Create resume"}
						</Button>
					)}
				</form.Subscribe>
			</div>

			{formError && (
				<p
					className="mt-3 rounded-xl bg-negative-bg px-4 py-2 text-negative text-sm"
					role="alert"
				>
					{formError}
				</p>
			)}

			<SectionPicker
				onAdd={(section) => setSections((current) => [...current, section])}
				onMove={(sectionId, direction) =>
					setSections((current) => {
						const index = current.findIndex(
							(section) => section.id === sectionId,
						);
						const swapWith = direction === "up" ? index - 1 : index + 1;
						if (index === -1 || swapWith < 0 || swapWith >= current.length) {
							return current;
						}

						const next = [...current];
						[next[index], next[swapWith]] = [next[swapWith], next[index]];
						return next;
					})
				}
				onRemove={(sectionId) =>
					setSections((current) =>
						current.filter((section) => section.id !== sectionId),
					)
				}
				sections={sections}
			/>
		</form>
	);
}

export default function Resumes() {
	const { data, isPending, isError } = $api.useQuery("get", "/resumes/");

	return (
		<main className="mx-auto w-full max-w-3xl px-4 py-16">
			<Link
				className="inline-flex items-center gap-1 text-sm text-ink-subtle transition-colors hover:text-ink"
				to="/dashboard"
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
				<span className="text-trim">Back to dashboard</span>
			</Link>

			<h1 className="mt-4 text-4xl leading-heading tracking-decreased">
				Resumes
			</h1>

			<CreateResumeForm />

			{isError && (
				<p
					className="mt-4 rounded-xl bg-negative-bg px-4 py-2 text-negative text-sm"
					role="alert"
				>
					Couldn't load your resumes. Try refreshing the page.
				</p>
			)}

			<Table
				columns={[
					{
						key: "name",
						header: "Name",
						render: (resume: Resume) => resume.name,
					},
					{
						key: "updatedAt",
						header: "Last modified",
						render: (resume: Resume) =>
							dateFormatter.format(new Date(resume.updated_at)),
					},
				]}
				data={data ?? []}
				emptyMessage={isPending ? "Loading…" : "No resumes yet."}
				getRowKey={(resume) => resume.id}
				className="mt-8"
			/>
		</main>
	);
}
