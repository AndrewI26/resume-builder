import { Table } from "@components/table";
import { Link } from "react-router";

export function meta() {
	return [{ title: "Resumes · Resume Builder" }];
}

type Resume = {
	id: string;
	name: string;
	updatedAt: string;
};

// Sample data — there's no backend endpoint for resumes yet, so this is
// hardcoded until one exists.
const SAMPLE_RESUMES: Resume[] = [
	{
		id: "1",
		name: "Software Engineer — General",
		updatedAt: "2026-08-20T14:30:00Z",
	},
	{
		id: "2",
		name: "Frontend Focused",
		updatedAt: "2026-08-15T09:12:00Z",
	},
	{
		id: "3",
		name: "Staff+ / Leadership",
		updatedAt: "2026-07-30T18:45:00Z",
	},
];

const dateFormatter = new Intl.DateTimeFormat("en-US", { dateStyle: "medium" });

export default function Resumes() {
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
			<p className="mt-2 text-ink-subtle">
				Showing sample data — resume storage isn't wired up yet.
			</p>

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
							dateFormatter.format(new Date(resume.updatedAt)),
					},
				]}
				data={SAMPLE_RESUMES}
				getRowKey={(resume) => resume.id}
				className="mt-8"
			/>
		</main>
	);
}
