import { Link } from "react-router";

export function meta() {
	return [{ title: "Page not found · Resume Builder" }];
}

export default function NotFound() {
	return (
		<main className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-3xl flex-col items-center justify-center px-4 py-16 text-center">
			<p className="text-sm tracking-increased text-ink-subtle uppercase">
				404
			</p>
			<h1 className="mt-4 text-4xl leading-heading tracking-decreased">
				Page not found
			</h1>
			<p className="mt-2 text-ink-subtle">
				The page you're looking for doesn't exist.
			</p>
			<Link
				className="mt-8 inline-flex h-10 items-center justify-center rounded-button bg-btn-primary px-4 text-btn-primary-fg transition-opacity hover:opacity-90"
				to="/"
			>
				<span className="text-trim">Go home</span>
			</Link>
		</main>
	);
}
