import { Button } from "@components/button";
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
		<main className="mx-auto w-full max-w-3xl px-4 py-16">
			<h1 className="text-4xl leading-heading tracking-decreased">Dashboard</h1>
			<p className="mt-2 text-ink-subtle">Signed in as {user?.email}</p>

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
