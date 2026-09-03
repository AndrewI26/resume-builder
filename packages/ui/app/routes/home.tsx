import type { ReactNode } from "react";
import { Link, Navigate } from "react-router";
import { useAuth } from "~/auth/auth-context";
import { isDesktop } from "~/platform/host";

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
	// The desktop app opens straight into the library. This page exists to
	// explain the product to somebody deciding whether to use it — which, in an
	// application they have already installed and can use offline without an
	// account, is a page about a decision they have made.
	if (isDesktop) {
		return <Navigate replace to="/dashboard" />;
	}

	return (
		<main className="mx-auto w-full max-w-6xl px-6">
			{/* Hero ------------------------------------------------------------ */}
			<section className="pt-20 pb-16 text-center sm:pt-28">
				<p className="text-sm text-ink-subtle uppercase tracking-increased">
					Resume Builder
				</p>

				<h1 className="mx-auto mt-6 max-w-3xl text-5xl leading-heading tracking-decreased sm:text-6xl lg:text-7xl">
					Write it once. Version it forever.
				</h1>

				<p className="mx-auto mt-6 max-w-xl text-ink-subtle text-lg leading-body sm:text-xl">
					Keep every role, project and bullet point in one library, then tailor
					a typeset resume for each application without losing the original.
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

			{/* Features --------------------------------------------------------- */}
			<Feature
				alt="The sections page, listing education and experience entries in tables"
				eyebrow="One library"
				shot="sections"
				title="Everything you've done, in one place"
			>
				<p>
					Education, experience, projects, skills and contact details live in a
					single library rather than inside one particular document. Add a role
					once and use it in as many resumes as you like.
				</p>
				<p className="mt-4">
					Edit it in the library and every resume built on it follows along —
					there is no copy to keep in sync.
				</p>
			</Feature>

			<Feature
				alt="The resumes page, listing two resumes with a form for creating another"
				eyebrow="Many versions"
				reversed
				shot="resumes"
				title="A version for every application"
			>
				<p>
					Build a resume by choosing sections from your library and putting them
					in the order you want. Each one keeps its own selection, its own
					ordering and its own header.
				</p>
				<p className="mt-4">
					Tailoring one for a frontend role leaves the backend version exactly
					as you left it.
				</p>
			</Feature>

			<Feature
				alt="Editing an experience entry, with bullet points and a bold-formatting preview"
				eyebrow="The writing"
				shot="section-form"
				title="Bullets worth reading"
			>
				<p>
					Write bullet points with the emphasis where it belongs — select any
					phrase and bold it with ⌘B, with a live preview of how it will
					typeset.
				</p>
				<p className="mt-4">
					Drag to reorder them, and drag whole sections to reorder those. The
					resume follows the arrangement you can see.
				</p>
			</Feature>

			{/* Smaller pair ----------------------------------------------------- */}
			<section className="py-20 lg:py-28">
				<h2 className="max-w-2xl text-4xl leading-heading tracking-decreased sm:text-5xl">
					Careful where it counts
				</h2>
				<p className="mt-5 max-w-lg text-ink-subtle text-lg leading-body">
					A resume is work you cannot get back by accident, so the destructive
					paths ask first and the rest stay out of your way.
				</p>

				<div className="mt-12 grid gap-8 md:grid-cols-2">
					<figure>
						<Shot
							alt="A confirmation dialog asking whether to delete a resume"
							name="confirm"
						/>
						<figcaption className="mt-4 text-ink-subtle leading-body">
							Deleting a resume names the one you picked and says what survives:
							the sections it used stay in your library.
						</figcaption>
					</figure>

					<figure>
						<Shot
							alt="The dashboard, showing counts of resumes and sections"
							name="dashboard"
						/>
						<figcaption className="mt-4 text-ink-subtle leading-body">
							The dashboard is a count and two doors — what you have, and where
							to go next.
						</figcaption>
					</figure>
				</div>
			</section>

			{/* Details ---------------------------------------------------------- */}
			<section className="border-border border-t py-20 lg:py-28">
				<h2 className="max-w-2xl text-4xl leading-heading tracking-decreased sm:text-5xl">
					The rest of it
				</h2>

				<div className="mt-12 grid gap-x-12 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
					<Detail title="Real typesetting">
						Resumes are compiled by a LaTeX engine from your saved sections, not
						approximated in the browser.
					</Detail>
					<Detail title="PDF and source">
						Download the finished PDF, or the .tex behind it if you would rather
						keep going by hand.
					</Detail>
					<Detail title="Drag to reorder">
						Sections within a resume, and bullet points within an entry, move by
						dragging.
					</Detail>
					<Detail title="Saves as you go">
						Edits to a resume save on their own — the editor tells you when
						everything has landed.
					</Detail>
					<Detail title="Light and dark">
						The whole app follows your system, or whichever you pick.
					</Detail>
					<Detail title="Your own header">
						Each resume carries its own name and contact block, so a personal
						address never leaks into a work application.
					</Detail>
				</div>
			</section>

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
