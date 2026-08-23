import { Button } from "@components/button";
import { Link, useNavigate } from "react-router";
import { useAuth } from "~/auth/auth-context";

export function meta() {
	return [{ title: "Dashboard · Resume Builder" }];
}

export default function Dashboard() {
	const { user, signOut } = useAuth();
	const navigate = useNavigate();

	return (
		<main className="mx-auto w-full max-w-3xl px-4 py-16">
			<h1 className="text-4xl leading-heading tracking-decreased">Dashboard</h1>
			<p className="mt-2 text-ink-subtle">Signed in as {user?.email}</p>

			<div className="mt-8 flex gap-4">
				<Link
					className="inline-flex h-10 items-center justify-center rounded-button border border-btn-secondary-border bg-btn-secondary px-4 text-btn-secondary-fg transition-colors hover:border-stroke"
					to="/resumes"
				>
					<span className="text-trim">Resumes</span>
				</Link>
				<Link
					className="inline-flex h-10 items-center justify-center rounded-button border border-btn-secondary-border bg-btn-secondary px-4 text-btn-secondary-fg transition-colors hover:border-stroke"
					to="/sections"
				>
					<span className="text-trim">Sections</span>
				</Link>
			</div>

			<Button
				className="mt-4"
				onClick={async () => {
					await signOut();
					navigate("/login", { replace: true });
				}}
				variant="tertiary"
			>
				Sign out
			</Button>
		</main>
	);
}
