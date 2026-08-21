import { useNavigate } from "react-router";
import { useAuth } from "~/auth/auth-context";
import { RequireAuth } from "~/auth/require-auth";

export function meta() {
	return [{ title: "Dashboard · Resume Builder" }];
}

function Dashboard() {
	const { user, signOut } = useAuth();
	const navigate = useNavigate();

	return (
		<main className="mx-auto w-full max-w-3xl px-md py-xl">
			<h1 className="font-display text-4xl leading-heading tracking-decreased">
				Dashboard
			</h1>
			<p className="mt-sm text-ink-subtle">Signed in as {user?.email}</p>

			<button
				className="mt-lg rounded-button bg-btn-tertiary px-md py-sm text-btn-tertiary-fg transition-opacity hover:opacity-90"
				onClick={async () => {
					await signOut();
					navigate("/login", { replace: true });
				}}
				type="button"
			>
				Sign out
			</button>
		</main>
	);
}

export default function DashboardRoute() {
	return (
		<RequireAuth>
			<Dashboard />
		</RequireAuth>
	);
}
