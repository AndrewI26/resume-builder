import type { ReactNode } from "react";
import { Link } from "react-router";
import { useAuth } from "~/auth/auth-context";
import { ReorderDemo } from "~/components/landing/reorder-demo";
import { ReuseDemo } from "~/components/landing/reuse-demo";
import { VersionsDemo } from "~/components/landing/versions-demo";

export function meta() {
	return [
		{ title: "Resume Builder" },
		{
			name: "description",
			content:
				"Keep every role, project and bullet point in one library, then tailor a typeset resume for each application without losing the original.",
		},
	];
}

/**
 * Intrinsic size of each capture, in CSS pixels — the files themselves are 2x.
 *
 * Stating it keeps the page from reflowing as the images arrive. Most are
 * cropped to their content rather than shot full-viewport: the app centres
 * itself in a wide column, and the empty canvas either side would otherwise
 * read as a tiny UI once the image sits in a half-width column here.
 */
const SHOTS = {
	editor: { width: 1440, height: 900 },
	// the hero at phone width: a real capture of the app's own single-column
	// layout, not a crop — see `HeroShot`
	"editor-mobile": { width: 390, height: 594 },
	sections: { width: 816, height: 760 },
	resumes: { width: 816, height: 820 },
	"section-form": { width: 784, height: 683 },
	confirm: { width: 688, height: 424 },
	dashboard: { width: 816, height: 533 },
} as const;

type ShotName = keyof typeof SHOTS;

/**
 * A product screenshot, in the palette the visitor is actually reading in.
 *
 * Theme here is a class on the root element rather than a media query alone,
 * so `<picture media>` would not follow the toggle. Two images swapped by the
 * `dark:` variant do, at the cost of a second file — hence `loading="lazy"`
 * on everything but the one above the fold.
 */
function Shot({
	name,
	alt,
	priority = false,
}: {
	name: ShotName;
	alt: string;
	priority?: boolean;
}) {
	// spelled out on each image rather than spread from a shared object, so the
	// a11y lint can see the alt text it is checking for
	const loading = priority ? "eager" : "lazy";
	const decoding = priority ? "sync" : "async";
	const { width, height } = SHOTS[name];

	// whichever image the theme hides is `display: none`, so it leaves the
	// accessibility tree and the alt text is announced once, not twice
	return (
		<div className="overflow-hidden rounded-card border border-border bg-card shadow-raised">
			<img
				alt={alt}
				className="w-full dark:hidden"
				decoding={decoding}
				height={height}
				loading={loading}
				src={`/shots/light/${name}.webp`}
				width={width}
			/>
			<img
				alt={alt}
				className="hidden w-full dark:block"
				decoding={decoding}
				height={height}
				loading={loading}
				src={`/shots/dark/${name}.webp`}
				width={width}
			/>
		</div>
	);
}

const HERO_ALT =
	"The resume editor, with the compiled PDF of the resume alongside the sections it was built from";

/**
 * The hero screenshot, which needs a second axis the others don't.
 *
 * The desktop capture is a 1440px-wide two-pane layout; scaled into a phone it
 * is a texture rather than a picture. The app reflows to a single column at
 * that width, so the small-screen variant is its own capture of the compiled
 * preview — the half that shows what the app is actually for.
 *
 * The breakpoint is a genuine media query, so `<picture>` resolves it natively
 * and fetches only the matching source. Theme is a class on the root element,
 * which `<picture media>` cannot follow, so that axis stays a `dark:` swap —
 * one `<picture>` per palette. `loading="lazy"` is what keeps the hidden one
 * from downloading at all: an eager image is fetched even under `display:none`.
 * The hero is in the initial viewport, where lazy images load immediately
 * anyway, and `fetchPriority` keeps it at the front of the queue.
 */
function HeroShot() {
	const wide = SHOTS.editor;
	const narrow = SHOTS["editor-mobile"];

	const forTheme = (theme: "light" | "dark") => (
		<>
			<source
				height={narrow.height}
				media="(max-width: 639px)"
				srcSet={`/shots/${theme}/editor-mobile.webp`}
				width={narrow.width}
			/>
			<img
				alt={HERO_ALT}
				className="w-full"
				decoding="async"
				fetchPriority="high"
				height={wide.height}
				loading="lazy"
				src={`/shots/${theme}/editor.webp`}
				width={wide.width}
			/>
		</>
	);

	return (
		<div className="overflow-hidden rounded-card border border-border bg-card shadow-raised">
			<picture className="dark:hidden">{forTheme("light")}</picture>
			<picture className="hidden dark:block">{forTheme("dark")}</picture>
		</div>
	);
}

function Feature({
	eyebrow,
	title,
	children,
	shot,
	alt,
	reversed = false,
}: {
	eyebrow: string;
	title: string;
	children: ReactNode;
	shot: ShotName;
	alt: string;
	reversed?: boolean;
}) {
	return (
		<section className="grid items-center gap-12 py-20 lg:grid-cols-2 lg:gap-20 lg:py-28">
			<div className={reversed ? "lg:order-2" : undefined}>
				<p className="text-sm text-ink-subtle uppercase tracking-increased">
					{eyebrow}
				</p>
				<h2 className="mt-4 text-4xl leading-heading tracking-decreased sm:text-5xl">
					{title}
				</h2>
				<div className="mt-5 max-w-lg text-ink-subtle text-lg leading-body">
					{children}
				</div>
			</div>

			<div className={reversed ? "lg:order-1" : undefined}>
				<Shot alt={alt} name={shot} />
			</div>
		</section>
	);
}

/** An interactive demo under its heading: the claim first, then the proof. */
function DemoSection({
	eyebrow,
	title,
	children,
	demo,
}: {
	eyebrow: string;
	title: string;
	children: ReactNode;
	demo: ReactNode;
}) {
	return (
		<section className="py-20 lg:py-28">
			<p className="text-sm text-ink-subtle uppercase tracking-increased">
				{eyebrow}
			</p>
			<h2 className="mt-4 max-w-2xl text-4xl leading-heading tracking-decreased sm:text-5xl">
				{title}
			</h2>
			<p className="mt-5 max-w-xl text-ink-subtle text-lg leading-body">
				{children}
			</p>
			<div className="mt-12">{demo}</div>
		</section>
	);
}

function Detail({ title, children }: { title: string; children: ReactNode }) {
	return (
		<div>
			<h3 className="text-lg tracking-decreased">{title}</h3>
			<p className="mt-2 text-ink-subtle leading-body">{children}</p>
		</div>
	);
}

function PrimaryLink({ to, children }: { to: string; children: ReactNode }) {
	return (
		<Link
			className="inline-flex h-12 items-center justify-center rounded-button bg-btn-primary px-7 text-btn-primary-fg transition-opacity hover:opacity-90"
			to={to}
		>
			<span className="text-trim">{children}</span>
		</Link>
	);
}

function SecondaryLink({ to, children }: { to: string; children: ReactNode }) {
	return (
		<Link
			className="inline-flex h-12 items-center justify-center rounded-button border border-btn-secondary-border bg-btn-secondary px-7 text-btn-secondary-fg transition-colors hover:border-stroke"
			to={to}
		>
			<span className="text-trim">{children}</span>
		</Link>
	);
}

function Cta() {
	const { isAuthenticated, isLoading, user } = useAuth();

	// reserve the row's height while auth resolves, so the hero does not jump
	if (isLoading) {
		return <div className="h-12" />;
	}

	if (isAuthenticated) {
		return (
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center">
				<PrimaryLink to="/dashboard">Go to dashboard</PrimaryLink>
				<p className="text-ink-subtle text-sm">Signed in as {user?.email}</p>
			</div>
		);
	}

	return (
		<div className="flex flex-col gap-3 sm:flex-row">
			<PrimaryLink to="/signup">Create an account</PrimaryLink>
			<SecondaryLink to="/login">Sign in</SecondaryLink>
		</div>
	);
}

export default function Home() {
	return (
		<main className="mx-auto w-full max-w-6xl px-6">
			{/* Hero ------------------------------------------------------------ */}
			<section className="pt-20 pb-16 text-center sm:pt-28">
				<p className="text-sm text-ink-subtle uppercase tracking-increased">
					Resume Builder
				</p>

				<h1 className="mx-auto mt-6 max-w-3xl text-5xl leading-heading tracking-decreased sm:text-6xl lg:text-7xl">
					Manage resumes with ease.
				</h1>

				<p className="mx-auto mt-6 max-w-xl text-ink-subtle text-lg leading-body sm:text-xl">
					Define every role, project and bullet point once, then create resumes
					that point to these sections.
				</p>

				<div className="mt-9 flex justify-center">
					<Cta />
				</div>
			</section>

			<div className="pb-8">
				<HeroShot />
			</div>

			<p className="pb-16 text-center text-ink-subtle text-sm">
				Your sections, typeset by LaTeX, previewed as you work.
			</p>

			{/* Demos ------------------------------------------------------------ */}
			<DemoSection
				eyebrow="One library"
				title="Define it once. Use it everywhere."
				demo={<ReuseDemo />}
			>
				Every role, project and skill lives in one library. A resume holds a
				reference to an entry, not a copy of it. So a fix made once lands on
				every resume that uses it.
			</DemoSection>

			<DemoSection
				eyebrow="Any order"
				title="Move sections where they matter"
				demo={<ReorderDemo />}
			>
				Lead with experience for one role and with education for the next. Drag
				a heading and the page follows; the library underneath does not move at
				all.
			</DemoSection>

			<DemoSection
				eyebrow="Many versions"
				title="A version for every application"
				demo={<VersionsDemo />}
			>
				Each resume keeps its own selection and its own order, drawn from the
				same library. Tailoring the platform version leaves the frontend one
				exactly as you left it.
			</DemoSection>

			{/* Close ------------------------------------------------------------ */}
			<section className="border-border border-t py-24 text-center lg:py-32">
				<h2 className="mx-auto max-w-2xl text-4xl leading-heading tracking-decreased sm:text-5xl">
					Start with one resume. Keep every version after it.
				</h2>

				<div className="mt-9 flex justify-center">
					<Cta />
				</div>
			</section>
		</main>
	);
}
