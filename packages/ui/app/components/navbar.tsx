import { Link } from "react-router";
import { canSync } from "~/platform/host";
import { useAuth } from "~/auth/auth-context";
import { ThemeToggle } from "~/components/theme-toggle";

function ProfileLink() {
	return (
		<Link
			aria-label="Profile"
			className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-btn-tertiary text-btn-tertiary-fg transition-opacity hover:opacity-90"
			title="Profile"
			to="/profile"
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
				<circle cx="12" cy="8" r="4" />
				<path d="M4 21a8 8 0 0 1 16 0" />
			</svg>
		</Link>
	);
}

/**
 * Only on the desktop: the browser app has no second copy of anything, so a
 * link to reconcile them would lead to a screen explaining that it cannot.
 */
function SyncLink() {
	return (
		<Link
			className="rounded-full px-3 py-1.5 text-ink-subtle text-sm hover:text-ink"
			to="/sync"
		>
			Sync
		</Link>
	);
}

export function Navbar() {
	const { isAuthenticated } = useAuth();

	return (
		<header className="w-full">
			<div className="flex h-16 w-full items-center justify-between px-4">
				<Link className="text-trim text-lg tracking-decreased" to="/">
					Resume Builder
				</Link>
				<div className="flex items-center gap-2">
					<ThemeToggle />
					{canSync && <SyncLink />}
					{isAuthenticated && <ProfileLink />}
				</div>
			</div>
		</header>
	);
}
