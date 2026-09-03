import { $api } from "@api/api";
import type { components } from "@api/schema.d.ts";
import { Button } from "@components/button";
import { ConfirmDialog } from "@components/confirm-dialog";
import { Dropdown, type DropdownOption } from "@components/dropdown";
import { Table } from "@components/table";
import { useForm } from "@tanstack/react-form";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router";

export function meta() {
	return [{ title: "Resumes · Resume Builder" }];
}

type Resume = components["schemas"]["ResumeRead"];
type ResumeError =
	| components["schemas"]["ErrorDetail"]
	| components["schemas"]["HTTPValidationError"];

function resumeErrorMessage(error: unknown, fallback: string): string {
	const detail = (error as ResumeError | undefined)?.detail;

	if (typeof detail === "string") {
		return detail;
	}

	if (Array.isArray(detail) && detail.length > 0) {
		return detail.map((item) => item.msg).join(" ");
	}

	return fallback;
}

const dateFormatter = new Intl.DateTimeFormat("en-US", { dateStyle: "medium" });

// The only template the renderer implements today. Stated explicitly rather
// than left to the server's default, so adding a second one surfaces here.
const DEFAULT_TEMPLATE = "jakes";

// Mirrors the API's ResumeSectionType. Personal info is deliberately absent:
// it is the header of a resume — name, email, links, no section heading — and
// is attached through personal_info_id rather than as a section.
type SectionType = "education" | "experience" | "project" | "skill";

const SECTION_TYPES: DropdownOption<SectionType>[] = [
	{ value: "education", label: "Education" },
	{ value: "experience", label: "Experience" },
	{ value: "project", label: "Project" },
	{ value: "skill", label: "Skill" },
];

type SectionOption = { id: string; label: string };

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
		<div className="mt-6 rounded-xl border border-border bg-table p-4">
			<p className="text-ink-subtle text-sm">Sections</p>

			<div className="mt-2 flex items-end gap-3">
				<Dropdown
					className="flex-1"
					id="section-type"
					label="Section type"
					onChange={(nextType) => {
						setSectionType(nextType);
						setSectionId("");
					}}
					options={SECTION_TYPES}
					placeholder="Choose a type…"
					value={sectionType}
				/>

				<Dropdown
					className="flex-1"
					disabled={sectionType === ""}
					emptyMessage={
						isLoading ? "Loading…" : "Nothing left to add for this type."
					}
					id="section-item"
					label="Section"
					onChange={setSectionId}
					options={availableOptions.map((option) => ({
						value: option.id,
						label: option.label,
					}))}
					placeholder={isLoading ? "Loading…" : "Choose a section…"}
					value={sectionId}
				/>

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

/**
 * The fields that make up the top of the printed resume.
 *
 * Personal info is not a section: it renders as the header — name, email,
 * links — with no section heading, which is why it is chosen here rather than
 * from the section picker. Without it a resume prints with a bare name and no
 * way to contact anyone.
 */
function HeaderFields({
	fullName,
	onFullNameChange,
	personalInfoId,
	onPersonalInfoChange,
}: {
	fullName: string;
	onFullNameChange: (value: string) => void;
	personalInfoId: string;
	onPersonalInfoChange: (value: string) => void;
}) {
	const { data, isPending } = $api.useQuery("get", "/personal-info/");

	const options = (data ?? []).map((row) => ({
		value: row.id,
		label:
			row.email ??
			row.address ??
			row.github?.label ??
			row.github?.url ??
			"Contact details",
	}));

	return (
		<div className="mt-6 rounded-xl border border-border bg-table p-4">
			<p className="text-ink-subtle text-sm">Header</p>

			<div className="mt-2 flex items-end gap-3">
				<div className="flex flex-1 flex-col gap-1">
					<label className="text-ink-subtle text-sm" htmlFor="full-name">
						Name on the resume
					</label>
					<input
						className="w-full rounded-xl border border-border bg-field px-4 py-field text-ink outline-none transition-colors placeholder:text-ink-disabled focus:border-stroke"
						id="full-name"
						name="full-name"
						onChange={(event) => onFullNameChange(event.target.value)}
						placeholder="e.g. Casey Quinn"
						value={fullName}
					/>
				</div>

				<Dropdown
					className="flex-1"
					emptyMessage="Add your contact details under Sections first."
					id="personal-info"
					label="Contact details"
					onChange={onPersonalInfoChange}
					options={options}
					placeholder={isPending ? "Loading…" : "Choose contact details…"}
					value={personalInfoId}
				/>
			</div>
		</div>
	);
}

function CreateResumeForm() {
	const queryClient = useQueryClient();
	const [formError, setFormError] = useState<string | null>(null);
	const [sections, setSections] = useState<
		(SectionOption & { type: SectionType })[]
	>([]);
	const [fullName, setFullName] = useState("");
	const [personalInfoId, setPersonalInfoId] = useState("");
	const { mutateAsync: createResume } = $api.useMutation("post", "/resumes/");

	const form = useForm({
		defaultValues: { name: "" },
		onSubmit: async ({ value, formApi }) => {
			setFormError(null);
			try {
				await createResume({
					body: {
						title: value.name,
						template: DEFAULT_TEMPLATE,
						// both drive the printed header; left null the resume
						// renders with no name and no way to contact anyone
						full_name: fullName.trim() || null,
						personal_info_id: personalInfoId || null,
						// the type travels with the id: without it nothing
						// downstream can tell a project from an education, and
						// the resume cannot be rendered
						sections: sections.map((section) => ({
							section_type: section.type,
							section_id: section.id,
						})),
					},
				});
				await queryClient.invalidateQueries({
					queryKey: $api.queryOptions("get", "/resumes/").queryKey,
				});
				formApi.reset();
				setSections([]);
				setFullName("");
				setPersonalInfoId("");
			} catch (error) {
				setFormError(
					resumeErrorMessage(
						error,
						"Could not create the resume. Please try again.",
					),
				);
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
								className="w-full rounded-xl border border-border bg-field px-4 py-field text-ink outline-none transition-colors placeholder:text-ink-disabled focus:border-stroke aria-invalid:border-negative"
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

			<HeaderFields
				fullName={fullName}
				onFullNameChange={setFullName}
				onPersonalInfoChange={setPersonalInfoId}
				personalInfoId={personalInfoId}
			/>

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
	const queryClient = useQueryClient();
	const { data, isPending, isError } = $api.useQuery("get", "/resumes/");
	// the whole row rather than an id: the dialog names the resume, and the
	// list has already been invalidated by the time the request comes back
	const [pendingDelete, setPendingDelete] = useState<Resume | null>(null);
	const [deleteError, setDeleteError] = useState<string | null>(null);
	const { mutateAsync: deleteResume, isPending: isDeleting } = $api.useMutation(
		"delete",
		"/resumes/{resume_id}",
	);

	const closeDeleteDialog = () => {
		setPendingDelete(null);
		setDeleteError(null);
	};

	const confirmDelete = async () => {
		if (pendingDelete === null) {
			return;
		}

		setDeleteError(null);
		try {
			await deleteResume({
				params: { path: { resume_id: pendingDelete.id } },
			});
			await queryClient.invalidateQueries({
				queryKey: $api.queryOptions("get", "/resumes/").queryKey,
			});
			closeDeleteDialog();
		} catch (error) {
			// the dialog stays open on failure, so the message has somewhere
			// to land and the action can be retried
			setDeleteError(
				resumeErrorMessage(error, "Could not delete the resume. Try again."),
			);
		}
	};

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
						render: (resume: Resume) => (
							<Link
								to={`/resumes/${resume.id}`}
								className="font-medium transition-colors hover:text-informative"
							>
								{resume.title}
							</Link>
						),
					},
					{
						key: "updatedAt",
						header: "Last modified",
						align: "right",
						render: (resume: Resume) =>
							dateFormatter.format(new Date(resume.updated_at)),
					},
					{
						key: "actions",
						header: "",
						align: "right",
						render: (resume: Resume) => (
							<button
								aria-label={`Delete ${resume.title}`}
								className="text-ink-subtle transition-colors hover:text-negative"
								onClick={() => {
									setDeleteError(null);
									setPendingDelete(resume);
								}}
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
						),
					},
				]}
				data={data ?? []}
				emptyMessage={isPending ? "Loading…" : "No resumes yet."}
				getRowKey={(resume) => resume.id}
				className="mt-8"
			/>

			<ConfirmDialog
				description={
					<>
						<strong className="text-ink">
							{pendingDelete?.title ?? "This resume"}
						</strong>{" "}
						will be deleted permanently. The education, experience, project and
						skill entries it uses stay in your sections.
					</>
				}
				error={deleteError}
				onCancel={closeDeleteDialog}
				onConfirm={confirmDelete}
				open={pendingDelete !== null}
				pending={isDeleting}
				title="Delete this resume?"
			/>
		</main>
	);
}
