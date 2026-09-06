import { $api } from "@api/api";
import { Button } from "@components/button";
import { StatCard } from "@components/stat-card";
import { useNavigate } from "react-router";
import { useAuth } from "~/auth/auth-context";
import { isDesktop } from "~/platform/host";

export function meta() {
	return [{ title: "Dashboard · Resume Builder" }];
}

function ResumeIcon() {
	return (
		<svg
			fill="none"
			height="20"
			stroke="currentColor"
			strokeLinecap="round"
			strokeLinejoin="round"
			strokeWidth="2"
			viewBox="0 0 24 24"
			width="20"
		>
			<title>Resume</title>
			<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
			<path d="M14 2v6h6M9 13h6M9 17h4" />
		</svg>
	);
}

function SectionsIcon() {
	return (
		<svg
			fill="none"
			height="20"
			stroke="currentColor"
			strokeLinecap="round"
			strokeLinejoin="round"
			strokeWidth="2"
			viewBox="0 0 24 24"
			width="20"
		>
			<title>Sections</title>
			<rect height="7" rx="1.5" width="18" x="3" y="3" />
			<rect height="7" rx="1.5" width="18" x="3" y="14" />
		</svg>
	);
}

/** Counts every saved section across the four section types.
 *
 * There is no single sections endpoint — each type lives behind its own path —
 * so this sums them. Personal info is deliberately left out: it prints as the
 * resume header rather than as a section, which is how the rest of the app
 * treats it too.
 */
function useSectionCount(): { count: number; isPending: boolean } {
	const education = $api.useQuery("get", "/education/");
	const experience = $api.useQuery("get", "/experience/");
	const project = $api.useQuery("get", "/project/");
	const skill = $api.useQuery("get", "/skill/");

	const queries = [education, experience, project, skill];

	return {
		count: queries.reduce(
			(total, query) => total + (query.data?.length ?? 0),
			0,
		),
		isPending: queries.some((query) => query.isPending),
	};
}

export default function Dashboard() {
	const { user, signOut } = useAuth();
	const navigate = useNavigate();
	const resumes = $api.useQuery("get", "/resumes/");
	const sections = useSectionCount();

	return (
		<main className="mx-auto w-full max-w-3xl px-4 py-16">
			<h1 className="text-4xl leading-heading tracking-decreased">Dashboard</h1>
			{/* the desktop has nobody signed in — the local user is bookkeeping,
			    not an account, and naming it would invent one */}
			{!isDesktop && (
				<p className="mt-2 text-ink-subtle">Signed in as {user?.email}</p>
			)}

			<div className="mt-8 grid gap-4 sm:grid-cols-2">
				<StatCard
					accent="blue"
					description="Tailored versions you can edit and export."
					icon={<ResumeIcon />}
					label="Resumes"
					to="/resumes"
					value={resumes.isPending ? "—" : (resumes.data?.length ?? 0)}
				/>
				<StatCard
					accent="green"
					description="Education, experience, projects and skills."
					icon={<SectionsIcon />}
					label="Sections"
					to="/sections"
					value={sections.isPending ? "—" : sections.count}
				/>
			</div>

			{/* nothing to sign out of on the desktop, and nowhere to land */}
			{!isDesktop && (
				<Button
					className="mt-8"
					onClick={async () => {
						await signOut();
						navigate("/login", { replace: true });
					}}
					variant="tertiary"
				>
					Sign out
				</Button>
			)}
		</main>
	);
}
