import type { Route } from "./+types/home";

export function meta(_: Route.MetaArgs) {
	return [
		{ title: "Resume Builder" },
		{ name: "description", content: "Build and version your resume." },
	];
}

export default function Home() {
	return (
		<main className="mx-auto max-w-3xl px-md py-xl">
			<h1 className="text-5xl leading-heading tracking-decreased">
				Resume Builder
			</h1>
		</main>
	);
}
