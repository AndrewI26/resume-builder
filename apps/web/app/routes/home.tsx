import { Link } from "react-router";
import { useAuth } from "~/auth/auth-context";

export function meta() {
	return [
		{ title: "Resume Builder" },
		{ name: "description", content: "Build and version your resume." },
	];
}

export default function Home() {
	const { isAuthenticated, isLoading, user } = useAuth();

	return (
		<main className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-3xl flex-col justify-center px-4 py-16">
			<p className="text-sm tracking-increased text-ink-subtle uppercase">
				Resume Builder
			</p>

			<h1 className="mt-4 text-5xl leading-heading tracking-decreased">
				Write it once. Version it forever.
			</h1>

			<p className="mt-4 max-w-xl text-lg leading-body text-ink-subtle">
				Keep every role, project and bullet point in one place, then tailor a
				version for each application without losing the original.
			</p>

			{isLoading ? (
				<div className="mt-8 h-12" />
			) : isAuthenticated ? (
				<div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center">
					<Link
						className="inline-flex h-12 items-center justify-center rounded-button bg-btn-primary px-6 text-btn-primary-fg transition-opacity hover:opacity-90"
						to="/dashboard"
					>
						<span className="text-trim">Go to dashboard</span>
					</Link>
					<p className="text-sm text-ink-subtle">Signed in as {user?.email}</p>
				</div>
			) : (
				<>
					<div className="mt-8 flex flex-col gap-4 sm:flex-row">
						<Link
							className="inline-flex h-12 items-center justify-center rounded-button bg-btn-primary px-6 text-btn-primary-fg transition-opacity hover:opacity-90"
							to="/login"
						>
							<span className="text-trim">Sign in</span>
						</Link>
						<Link
							className="inline-flex h-12 items-center justify-center rounded-button border border-btn-secondary-border bg-btn-secondary px-6 text-btn-secondary-fg transition-colors hover:border-stroke"
							to="/signup"
						>
							<span className="text-trim">Create an account</span>
						</Link>
					</div>
					<p className="mt-4 text-sm text-ink-subtle">
						You need an account to start building — sign in, or create one in a
						few seconds.
					</p>
				</>
			)}
		</main>
	);
}
