import { Link } from "react-router";
import { ThemeToggle } from "~/components/theme-toggle";

export function Navbar() {
	return (
		<header className="w-full">
			<div className="mx-auto flex h-16 w-full max-w-3xl items-center justify-between px-4">
				<Link className="text-trim text-lg tracking-decreased" to="/">
					Resume Builder
				</Link>
				<ThemeToggle />
			</div>
		</header>
	);
}
