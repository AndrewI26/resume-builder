import { $api } from "@api/api";
import { type Column, Table } from "@components/table";
import { Link, useNavigate } from "react-router";

export function meta() {
	return [{ title: "Sections · Resume Builder" }];
}

function joinOrDash(items: string[]): string {
	return items.length > 0 ? items.join(", ") : "—";
}

function AddSectionButton({ label, to }: { label: string; to: string }) {
	return (
		<Link
			aria-label={label}
			className="inline-flex h-8 w-8 items-center justify-center rounded-full text-ink-subtle transition-colors hover:bg-field hover:text-ink"
			to={to}
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
		</Link>
	);
}

function SectionTable<T extends { id: string }>({
	title,
	columns,
	data,
	isPending,
	isError,
	emptyMessage,
	addHref,
	rowHref,
}: {
	title: string;
	columns: Column<T>[];
	data: T[] | undefined;
	isPending: boolean;
	isError: boolean;
	emptyMessage: string;
	addHref: string;
	rowHref: (row: T) => string;
}) {
	const navigate = useNavigate();

	return (
		<section className="mt-10">
			<div className="flex items-center justify-between">
				<h2 className="text-2xl leading-heading tracking-decreased">{title}</h2>
				<AddSectionButton label={`Add ${title.toLowerCase()}`} to={addHref} />
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
				onRowClick={(row) => navigate(rowHref(row))}
			/>
		</section>
	);
}

export default function Sections() {
	const education = $api.useQuery("get", "/education/");
	const experience = $api.useQuery("get", "/experience/");
	const personalInfo = $api.useQuery("get", "/personal-info/");
	const project = $api.useQuery("get", "/project/");
	const skill = $api.useQuery("get", "/skill/");

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
				Everything you've added, grouped by section type. Click a row to edit or
				delete it.
			</p>

			<SectionTable
				addHref="/sections/education/new"
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
				rowHref={(row) => `/sections/education/${row.id}`}
				title="Education"
			/>

			<SectionTable
				addHref="/sections/experience/new"
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
				rowHref={(row) => `/sections/experience/${row.id}`}
				title="Experience"
			/>

			<SectionTable
				addHref="/sections/personal-info/new"
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
								[row.github, row.linkedin, row.portfolio]
									.filter(
										(link): link is NonNullable<typeof link> =>
											link !== null && link !== undefined,
									)
									.map((link) => link.label ?? link.url),
							),
					},
				]}
				data={personalInfo.data}
				emptyMessage="No personal info added yet."
				isError={personalInfo.isError}
				isPending={personalInfo.isPending}
				rowHref={(row) => `/sections/personal-info/${row.id}`}
				title="Personal info"
			/>

			<SectionTable
				addHref="/sections/project/new"
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
				rowHref={(row) => `/sections/project/${row.id}`}
				title="Projects"
			/>

			<SectionTable
				addHref="/sections/skill/new"
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
				rowHref={(row) => `/sections/skill/${row.id}`}
				title="Skills"
			/>
		</main>
	);
}
