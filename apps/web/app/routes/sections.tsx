import { $api } from "@api/api";
import type { components } from "@api/schema.d.ts";
import { Button } from "@components/button";
import { Modal } from "@components/modal";
import { type Column, Table } from "@components/table";
import { useForm } from "@tanstack/react-form";
import { useQueryClient } from "@tanstack/react-query";
import {
	type InputHTMLAttributes,
	type ReactNode,
	useId,
	useState,
} from "react";
import { Link } from "react-router";

export function meta() {
	return [{ title: "Sections · Resume Builder" }];
}

function joinOrDash(items: string[]): string {
	return items.length > 0 ? items.join(", ") : "—";
}

function splitList(text: string): string[] {
	return text
		.split(",")
		.map((item) => item.trim())
		.filter((item) => item.length > 0);
}

function toBulletPoints(text: string): { text: string; bolded: [] }[] {
	return text
		.split("\n")
		.map((line) => line.trim())
		.filter((line) => line.length > 0)
		.map((line) => ({ text: line, bolded: [] }));
}

function required(message: string) {
	return ({ value }: { value: string }) =>
		value.trim().length > 0 ? undefined : message;
}

type SectionError =
	| components["schemas"]["ErrorDetail"]
	| components["schemas"]["HTTPValidationError"];

function sectionErrorMessage(error: unknown, fallback: string): string {
	const detail = (error as SectionError | undefined)?.detail;

	if (typeof detail === "string") {
		return detail;
	}

	if (Array.isArray(detail) && detail.length > 0) {
		return detail.map((item) => item.msg).join(" ");
	}

	return fallback;
}

const inputClassName =
	"w-full rounded-xl border border-border bg-field px-4 py-2 text-ink outline-none transition-colors placeholder:text-ink-disabled focus:border-stroke aria-invalid:border-negative";

function TextInput({
	error,
	label,
	...inputProps
}: {
	error?: string;
	label: string;
} & InputHTMLAttributes<HTMLInputElement>) {
	const id = useId();

	return (
		<div className="flex flex-col gap-1">
			<label className="text-ink-subtle text-sm" htmlFor={id}>
				{label}
			</label>
			<input
				aria-invalid={error !== undefined}
				className={inputClassName}
				id={id}
				{...inputProps}
			/>
			{error !== undefined && <p className="text-negative text-sm">{error}</p>}
		</div>
	);
}

function TextArea({
	label,
	onChange,
	value,
}: {
	label: string;
	onChange: (value: string) => void;
	value: string;
}) {
	const id = useId();

	return (
		<div className="flex flex-col gap-1">
			<label className="text-ink-subtle text-sm" htmlFor={id}>
				{label}
			</label>
			<textarea
				className={`${inputClassName} min-h-24`}
				id={id}
				onChange={(event) => onChange(event.target.value)}
				value={value}
			/>
		</div>
	);
}

function FormError({ children }: { children: ReactNode }) {
	return (
		<p
			className="rounded-xl bg-negative-bg px-4 py-2 text-negative text-sm"
			role="alert"
		>
			{children}
		</p>
	);
}

function EducationForm({ onCreated }: { onCreated: () => void }) {
	const queryClient = useQueryClient();
	const [formError, setFormError] = useState<string | null>(null);
	const { mutateAsync: createEducation } = $api.useMutation(
		"post",
		"/education/",
	);

	const form = useForm({
		defaultValues: { name: "", subheading: "", duration: "", location: "" },
		onSubmit: async ({ value }) => {
			setFormError(null);
			try {
				await createEducation({ body: value });
				await queryClient.invalidateQueries({
					queryKey: $api.queryOptions("get", "/education/").queryKey,
				});
				onCreated();
			} catch (error) {
				setFormError(
					sectionErrorMessage(error, "Could not add education. Try again."),
				);
			}
		},
	});

	return (
		<form
			className="flex flex-col gap-4"
			noValidate
			onSubmit={(event) => {
				event.preventDefault();
				form.handleSubmit();
			}}
		>
			<form.Field
				name="name"
				validators={{ onSubmit: required("Enter a name.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Name"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="B.S. Computer Science"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field
				name="subheading"
				validators={{ onSubmit: required("Enter a subheading.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Subheading"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="University of Somewhere"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field
				name="duration"
				validators={{ onSubmit: required("Enter a duration.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Duration"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="2018 – 2022"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field
				name="location"
				validators={{ onSubmit: required("Enter a location.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Location"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="Remote"
						value={field.state.value}
					/>
				)}
			</form.Field>

			{formError && <FormError>{formError}</FormError>}

			<form.Subscribe
				selector={(state) => [state.canSubmit, state.isSubmitting] as const}
			>
				{([canSubmit, isSubmitting]) => (
					<Button disabled={!canSubmit} type="submit">
						{isSubmitting ? "Adding…" : "Add education"}
					</Button>
				)}
			</form.Subscribe>
		</form>
	);
}

function ExperienceForm({ onCreated }: { onCreated: () => void }) {
	const queryClient = useQueryClient();
	const [formError, setFormError] = useState<string | null>(null);
	const { mutateAsync: createExperience } = $api.useMutation(
		"post",
		"/experience/",
	);

	const form = useForm({
		defaultValues: {
			company: "",
			position: "",
			duration: "",
			location: "",
			bulletPointsText: "",
		},
		onSubmit: async ({ value }) => {
			setFormError(null);
			try {
				await createExperience({
					body: {
						company: value.company,
						position: value.position,
						duration: value.duration,
						location: value.location,
						bullet_points: toBulletPoints(value.bulletPointsText),
					},
				});
				await queryClient.invalidateQueries({
					queryKey: $api.queryOptions("get", "/experience/").queryKey,
				});
				onCreated();
			} catch (error) {
				setFormError(
					sectionErrorMessage(error, "Could not add experience. Try again."),
				);
			}
		},
	});

	return (
		<form
			className="flex flex-col gap-4"
			noValidate
			onSubmit={(event) => {
				event.preventDefault();
				form.handleSubmit();
			}}
		>
			<form.Field
				name="position"
				validators={{ onSubmit: required("Enter a position.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Position"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="Software Engineer"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field
				name="company"
				validators={{ onSubmit: required("Enter a company.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Company"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="Acme Corp"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field
				name="duration"
				validators={{ onSubmit: required("Enter a duration.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Duration"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="2022 – Present"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field
				name="location"
				validators={{ onSubmit: required("Enter a location.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Location"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="Remote"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field name="bulletPointsText">
				{(field) => (
					<TextArea
						label="Bullet points (one per line)"
						onChange={field.handleChange}
						value={field.state.value}
					/>
				)}
			</form.Field>

			{formError && <FormError>{formError}</FormError>}

			<form.Subscribe
				selector={(state) => [state.canSubmit, state.isSubmitting] as const}
			>
				{([canSubmit, isSubmitting]) => (
					<Button disabled={!canSubmit} type="submit">
						{isSubmitting ? "Adding…" : "Add experience"}
					</Button>
				)}
			</form.Subscribe>
		</form>
	);
}

function PersonalInfoForm({ onCreated }: { onCreated: () => void }) {
	const queryClient = useQueryClient();
	const [formError, setFormError] = useState<string | null>(null);
	const { mutateAsync: createPersonalInfo } = $api.useMutation(
		"post",
		"/personal-info/",
	);

	const form = useForm({
		defaultValues: {
			email: "",
			phone_number: "",
			address: "",
			github: "",
			linkedin: "",
			portfolio: "",
		},
		onSubmit: async ({ value }) => {
			setFormError(null);
			try {
				await createPersonalInfo({
					body: {
						email: value.email.trim() || undefined,
						phone_number: value.phone_number.trim() || undefined,
						address: value.address.trim() || undefined,
						github: value.github.trim() || undefined,
						linkedin: value.linkedin.trim() || undefined,
						portfolio: value.portfolio.trim() || undefined,
					},
				});
				await queryClient.invalidateQueries({
					queryKey: $api.queryOptions("get", "/personal-info/").queryKey,
				});
				onCreated();
			} catch (error) {
				setFormError(
					sectionErrorMessage(error, "Could not add personal info. Try again."),
				);
			}
		},
	});

	return (
		<form
			className="flex flex-col gap-4"
			noValidate
			onSubmit={(event) => {
				event.preventDefault();
				form.handleSubmit();
			}}
		>
			<form.Field name="email">
				{(field) => (
					<TextInput
						label="Email"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="you@example.com"
						type="email"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field name="phone_number">
				{(field) => (
					<TextInput
						label="Phone"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="555-555-5555"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field name="address">
				{(field) => (
					<TextInput
						label="Address"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="City, State"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field name="github">
				{(field) => (
					<TextInput
						label="GitHub"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="https://github.com/you"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field name="linkedin">
				{(field) => (
					<TextInput
						label="LinkedIn"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="https://linkedin.com/in/you"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field name="portfolio">
				{(field) => (
					<TextInput
						label="Portfolio"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="https://you.dev"
						value={field.state.value}
					/>
				)}
			</form.Field>

			{formError && <FormError>{formError}</FormError>}

			<form.Subscribe
				selector={(state) => [state.canSubmit, state.isSubmitting] as const}
			>
				{([canSubmit, isSubmitting]) => (
					<Button disabled={!canSubmit} type="submit">
						{isSubmitting ? "Adding…" : "Add personal info"}
					</Button>
				)}
			</form.Subscribe>
		</form>
	);
}

function ProjectForm({ onCreated }: { onCreated: () => void }) {
	const queryClient = useQueryClient();
	const [formError, setFormError] = useState<string | null>(null);
	const { mutateAsync: createProject } = $api.useMutation("post", "/project/");

	const form = useForm({
		defaultValues: {
			name: "",
			link: "",
			technologiesText: "",
			bulletPointsText: "",
		},
		onSubmit: async ({ value }) => {
			setFormError(null);
			try {
				await createProject({
					body: {
						name: value.name,
						link: value.link.trim() || undefined,
						technologies: splitList(value.technologiesText),
						bullet_points: toBulletPoints(value.bulletPointsText),
					},
				});
				await queryClient.invalidateQueries({
					queryKey: $api.queryOptions("get", "/project/").queryKey,
				});
				onCreated();
			} catch (error) {
				setFormError(
					sectionErrorMessage(error, "Could not add project. Try again."),
				);
			}
		},
	});

	return (
		<form
			className="flex flex-col gap-4"
			noValidate
			onSubmit={(event) => {
				event.preventDefault();
				form.handleSubmit();
			}}
		>
			<form.Field
				name="name"
				validators={{ onSubmit: required("Enter a name.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Name"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="Resume Builder"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field name="link">
				{(field) => (
					<TextInput
						label="Link"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="https://github.com/you/project"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field name="technologiesText">
				{(field) => (
					<TextInput
						label="Technologies (comma separated)"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="React, FastAPI, Postgres"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field name="bulletPointsText">
				{(field) => (
					<TextArea
						label="Bullet points (one per line)"
						onChange={field.handleChange}
						value={field.state.value}
					/>
				)}
			</form.Field>

			{formError && <FormError>{formError}</FormError>}

			<form.Subscribe
				selector={(state) => [state.canSubmit, state.isSubmitting] as const}
			>
				{([canSubmit, isSubmitting]) => (
					<Button disabled={!canSubmit} type="submit">
						{isSubmitting ? "Adding…" : "Add project"}
					</Button>
				)}
			</form.Subscribe>
		</form>
	);
}

function SkillForm({ onCreated }: { onCreated: () => void }) {
	const queryClient = useQueryClient();
	const [formError, setFormError] = useState<string | null>(null);
	const { mutateAsync: createSkill } = $api.useMutation("post", "/skill/");

	const form = useForm({
		defaultValues: { name: "", itemsText: "" },
		onSubmit: async ({ value }) => {
			setFormError(null);
			try {
				await createSkill({
					body: { name: value.name, items: splitList(value.itemsText) },
				});
				await queryClient.invalidateQueries({
					queryKey: $api.queryOptions("get", "/skill/").queryKey,
				});
				onCreated();
			} catch (error) {
				setFormError(
					sectionErrorMessage(error, "Could not add skill. Try again."),
				);
			}
		},
	});

	return (
		<form
			className="flex flex-col gap-4"
			noValidate
			onSubmit={(event) => {
				event.preventDefault();
				form.handleSubmit();
			}}
		>
			<form.Field
				name="name"
				validators={{ onSubmit: required("Enter a name.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Name"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="Languages"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field
				name="itemsText"
				validators={{ onSubmit: required("Enter at least one item.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Items (comma separated)"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="Python, Go, SQL"
						value={field.state.value}
					/>
				)}
			</form.Field>

			{formError && <FormError>{formError}</FormError>}

			<form.Subscribe
				selector={(state) => [state.canSubmit, state.isSubmitting] as const}
			>
				{([canSubmit, isSubmitting]) => (
					<Button disabled={!canSubmit} type="submit">
						{isSubmitting ? "Adding…" : "Add skill"}
					</Button>
				)}
			</form.Subscribe>
		</form>
	);
}

function AddSectionButton({
	label,
	onClick,
}: {
	label: string;
	onClick: () => void;
}) {
	return (
		<button
			aria-label={label}
			className="inline-flex h-8 w-8 items-center justify-center rounded-full text-ink-subtle transition-colors hover:bg-field hover:text-ink"
			onClick={onClick}
			type="button"
		>
			<svg
				aria-hidden="true"
				fill="none"
				height="18"
				stroke="currentColor"
				strokeLinecap="round"
				strokeLinejoin="round"
				strokeWidth="2"
				viewBox="0 0 24 24"
				width="18"
			>
				<path d="M12 5v14M5 12h14" />
			</svg>
		</button>
	);
}

function SectionTable<T extends { id: string }>({
	title,
	columns,
	data,
	isPending,
	isError,
	emptyMessage,
	onAdd,
}: {
	title: string;
	columns: Column<T>[];
	data: T[] | undefined;
	isPending: boolean;
	isError: boolean;
	emptyMessage: string;
	onAdd: () => void;
}) {
	return (
		<section className="mt-10">
			<div className="flex items-center justify-between">
				<h2 className="text-2xl leading-heading tracking-decreased">{title}</h2>
				<AddSectionButton
					label={`Add ${title.toLowerCase()}`}
					onClick={onAdd}
				/>
			</div>

			{isError && (
				<p
					className="mt-2 rounded-xl bg-negative-bg px-4 py-2 text-negative text-sm"
					role="alert"
				>
					Couldn't load {title.toLowerCase()}. Try refreshing the page.
				</p>
			)}

			<Table
				className="mt-4"
				columns={columns}
				data={data ?? []}
				emptyMessage={isPending ? "Loading…" : emptyMessage}
				getRowKey={(row) => row.id}
			/>
		</section>
	);
}

type SectionKind =
	| "education"
	| "experience"
	| "personal_info"
	| "project"
	| "skill";

export default function Sections() {
	const education = $api.useQuery("get", "/education/");
	const experience = $api.useQuery("get", "/experience/");
	const personalInfo = $api.useQuery("get", "/personal-info/");
	const project = $api.useQuery("get", "/project/");
	const skill = $api.useQuery("get", "/skill/");

	const [openModal, setOpenModal] = useState<SectionKind | null>(null);
	const closeModal = () => setOpenModal(null);

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
				Sections
			</h1>
			<p className="mt-2 text-ink-subtle">
				Everything you've added, grouped by section type.
			</p>

			<SectionTable
				columns={[
					{ key: "name", header: "Name", render: (row) => row.name },
					{
						key: "subheading",
						header: "Subheading",
						render: (row) => row.subheading,
					},
					{
						key: "duration",
						header: "Duration",
						render: (row) => row.duration,
					},
					{
						key: "location",
						header: "Location",
						render: (row) => row.location,
					},
				]}
				data={education.data}
				emptyMessage="No education added yet."
				isError={education.isError}
				isPending={education.isPending}
				onAdd={() => setOpenModal("education")}
				title="Education"
			/>

			<SectionTable
				columns={[
					{
						key: "position",
						header: "Position",
						render: (row) => row.position,
					},
					{ key: "company", header: "Company", render: (row) => row.company },
					{
						key: "duration",
						header: "Duration",
						render: (row) => row.duration,
					},
					{
						key: "location",
						header: "Location",
						render: (row) => row.location,
					},
				]}
				data={experience.data}
				emptyMessage="No experience added yet."
				isError={experience.isError}
				isPending={experience.isPending}
				onAdd={() => setOpenModal("experience")}
				title="Experience"
			/>

			<SectionTable
				columns={[
					{
						key: "email",
						header: "Email",
						render: (row) => row.email ?? "—",
					},
					{
						key: "phone_number",
						header: "Phone",
						render: (row) => row.phone_number ?? "—",
					},
					{
						key: "address",
						header: "Address",
						render: (row) => row.address ?? "—",
					},
					{
						key: "links",
						header: "Links",
						render: (row) =>
							joinOrDash(
								[row.github, row.linkedin, row.portfolio].filter(
									(link): link is string => link !== null && link !== undefined,
								),
							),
					},
				]}
				data={personalInfo.data}
				emptyMessage="No personal info added yet."
				isError={personalInfo.isError}
				isPending={personalInfo.isPending}
				onAdd={() => setOpenModal("personal_info")}
				title="Personal info"
			/>

			<SectionTable
				columns={[
					{ key: "name", header: "Name", render: (row) => row.name },
					{
						key: "technologies",
						header: "Technologies",
						render: (row) => joinOrDash(row.technologies),
					},
					{
						key: "link",
						header: "Link",
						render: (row) => row.link ?? "—",
					},
				]}
				data={project.data}
				emptyMessage="No projects added yet."
				isError={project.isError}
				isPending={project.isPending}
				onAdd={() => setOpenModal("project")}
				title="Projects"
			/>

			<SectionTable
				columns={[
					{ key: "name", header: "Name", render: (row) => row.name },
					{
						key: "items",
						header: "Items",
						render: (row) => joinOrDash(row.items),
					},
				]}
				data={skill.data}
				emptyMessage="No skills added yet."
				isError={skill.isError}
				isPending={skill.isPending}
				onAdd={() => setOpenModal("skill")}
				title="Skills"
			/>

			<Modal
				onClose={closeModal}
				open={openModal === "education"}
				title="Add education"
			>
				<EducationForm onCreated={closeModal} />
			</Modal>

			<Modal
				onClose={closeModal}
				open={openModal === "experience"}
				title="Add experience"
			>
				<ExperienceForm onCreated={closeModal} />
			</Modal>

			<Modal
				onClose={closeModal}
				open={openModal === "personal_info"}
				title="Add personal info"
			>
				<PersonalInfoForm onCreated={closeModal} />
			</Modal>

			<Modal
				onClose={closeModal}
				open={openModal === "project"}
				title="Add project"
			>
				<ProjectForm onCreated={closeModal} />
			</Modal>

			<Modal
				onClose={closeModal}
				open={openModal === "skill"}
				title="Add skill"
			>
				<SkillForm onCreated={closeModal} />
			</Modal>
		</main>
	);
}
