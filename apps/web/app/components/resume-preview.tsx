/**
 * An HTML replica of Jake's Resume template.
 *
 * Deliberately not a PDF. This renders instantly on every keystroke, which a
 * TeX compile cannot, so it is what the editor shows while someone is typing.
 * The authentic PDF comes from compiling the generated `.tex`.
 *
 * It is a close likeness rather than a pixel match: the browser's line
 * breaking and hyphenation are not TeX's, so a long bullet may wrap one word
 * differently. Everything structural — order, spacing, weights, the page box —
 * is modelled on the template's own measurements.
 */

import { splitBullet } from "~/lib/resume/bullet";
// shared with the editing panel: if the two disagreed, the panel would name a
// heading one thing and the page another
import { SECTION_TITLES } from "~/lib/resume/document";
import type {
	BulletPoint,
	Education,
	Experience,
	PersonalInfo,
	Project,
	ResumeDocument,
	SectionBlock,
	Skill,
} from "~/lib/resume/types";
import { typeset } from "~/lib/resume/typography";

function Bullets({ items }: { items: BulletPoint[] }) {
	if (items.length === 0) return null;

	return (
		// Bullet points carry no id of their own, and the API stores them as an
		// ordered array, so position genuinely is their identity. Nothing in the
		// subtree holds state that a reorder could strand.
		<ul className="resume-bullets">
			{items.map((bullet, index) => (
				// biome-ignore lint/suspicious/noArrayIndexKey: order is the identity
				<li key={index}>
					{splitBullet(bullet).map((segment) =>
						segment.bold ? (
							<strong key={segment.start}>{typeset(segment.text)}</strong>
						) : (
							<span key={segment.start}>{typeset(segment.text)}</span>
						),
					)}
				</li>
			))}
		</ul>
	);
}

/** The two-line, four-corner heading the template uses for jobs and schools. */
function Subheading({
	title,
	right,
	subtitle,
	subRight,
}: {
	title: string;
	right: string;
	subtitle: string;
	subRight: string;
}) {
	return (
		<div className="resume-subheading">
			<div className="resume-row resume-row-title">
				<span className="font-bold">{typeset(title)}</span>
				{/* \textbf{\small #2}: the date drops to \small, the title does not */}
				<span className="resume-subheading font-bold">{typeset(right)}</span>
			</div>
			<div className="resume-row italic">
				<span>{typeset(subtitle)}</span>
				<span>{typeset(subRight)}</span>
			</div>
		</div>
	);
}

function ContactEntry({ icon, label }: { icon: string; label: string }) {
	return (
		<span className="resume-contact-entry">
			<Icon name={icon} />
			<span className="resume-underline">{typeset(label)}</span>
		</span>
	);
}

/**
 * Stand-ins for the template's fontawesome glyphs.
 *
 * `\faLinkedin` and `\faGithub` are brand marks, not generic link glyphs, so
 * drawing them as chain links makes the contact line read wrong at a glance.
 * These are simplified outlines at the same optical weight as the text.
 */
function Icon({ name }: { name: string }) {
	if (name === "linkedin") {
		return (
			<svg
				className="resume-icon"
				viewBox="0 0 24 24"
				fill="currentColor"
				aria-hidden="true"
			>
				<path d="M20.4 0H3.6A3.6 3.6 0 0 0 0 3.6v16.8A3.6 3.6 0 0 0 3.6 24h16.8a3.6 3.6 0 0 0 3.6-3.6V3.6A3.6 3.6 0 0 0 20.4 0zM7.3 20H4.1V9.3h3.2V20zM5.7 7.9a1.9 1.9 0 1 1 0-3.8 1.9 1.9 0 0 1 0 3.8zM20 20h-3.2v-5.2c0-1.2 0-2.8-1.7-2.8s-2 1.4-2 2.8V20H9.9V9.3H13v1.5h.1a3.4 3.4 0 0 1 3-1.7c3.3 0 3.9 2.2 3.9 5V20z" />
			</svg>
		);
	}

	if (name === "github") {
		return (
			<svg
				className="resume-icon"
				viewBox="0 0 24 24"
				fill="currentColor"
				aria-hidden="true"
			>
				<path d="M12 .3a12 12 0 0 0-3.8 23.4c.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.4-1.8-1.4-1.8-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 0-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-5.9 0-1.3.5-2.4 1.2-3.2 0-.3-.5-1.5.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0C16.9 4.9 18 5.2 18 5.2c.6 1.7.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.6-2.8 5.6-5.5 5.9.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0 0 12 .3z" />
			</svg>
		);
	}

	const paths: Record<string, string> = {
		envelope: "M2 4h12v8H2z M2 4l6 4 6-4",
		globe:
			"M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1z M1 8h14 M8 1c4 4 4 10 0 14 M8 1C4 5 4 11 8 15",
		phone:
			"M3 2h3l1 4-2 1a9 9 0 0 0 4 4l1-2 4 1v3a1 1 0 0 1-1 1A12 12 0 0 1 2 3a1 1 0 0 1 1-1z",
		pin: "M8 1a4 4 0 0 0-4 4c0 3 4 9 4 9s4-6 4-9a4 4 0 0 0-4-4z M8 5.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z",
		link: "M6 10a3 3 0 0 0 4 0l3-3a3 3 0 0 0-4-4L8 4 M10 6a3 3 0 0 0-4 0L3 9a3 3 0 0 0 4 4l1-1",
	};

	return (
		<svg
			viewBox="0 0 16 16"
			className="resume-icon"
			fill="none"
			stroke="currentColor"
			strokeWidth="1.4"
			aria-hidden="true"
		>
			<path d={paths[name] ?? paths.globe} />
		</svg>
	);
}

/** Strip the scheme and any trailing slash, the way the template prints links. */
function displayUrl(url: string): string {
	return url.replace(/^https?:\/\//, "").replace(/\/$/, "");
}

/** A link's custom label if it has one, otherwise a fallback. */
function linkLabel(link: { label?: string | null }, fallback: string): string {
	return link.label ? link.label : fallback;
}

function Header({
	fullName,
	info,
}: {
	fullName: string;
	info: PersonalInfo | null | undefined;
}) {
	const entries: { icon: string; label: string }[] = [];

	if (info?.phone_number) {
		entries.push({ icon: "phone", label: info.phone_number });
	}
	if (info?.email) entries.push({ icon: "envelope", label: info.email });
	if (info?.linkedin) {
		entries.push({
			icon: "linkedin",
			label: linkLabel(info.linkedin, displayUrl(info.linkedin.url)),
		});
	}
	if (info?.github) {
		entries.push({
			icon: "github",
			label: linkLabel(info.github, displayUrl(info.github.url)),
		});
	}
	if (info?.portfolio) {
		entries.push({
			icon: "globe",
			label: linkLabel(info.portfolio, "Portfolio"),
		});
	}
	if (info?.address) entries.push({ icon: "pin", label: info.address });

	return (
		<header className="resume-header">
			<h1 className="resume-name">{typeset(fullName)}</h1>
			{entries.length > 0 && (
				<div className="resume-contact">
					{entries.map((entry) => (
						<ContactEntry
							key={`${entry.icon}-${entry.label}`}
							icon={entry.icon}
							label={entry.label}
						/>
					))}
				</div>
			)}
		</header>
	);
}

function Skills({ items }: { items: Skill[] }) {
	return (
		<div className="resume-skills">
			{items.map((skill) => (
				<div key={skill.id}>
					<strong>{typeset(skill.name)}</strong>:{" "}
					{typeset(skill.items.join(", "))}
				</div>
			))}
		</div>
	);
}

function Experiences({ items }: { items: Experience[] }) {
	return (
		<>
			{items.map((experience) => (
				<div key={experience.id} className="resume-entry">
					<Subheading
						title={experience.company}
						right={experience.duration}
						subtitle={experience.position}
						subRight={experience.location}
					/>
					<Bullets items={experience.bullet_points} />
				</div>
			))}
		</>
	);
}

function Projects({ items }: { items: Project[] }) {
	return (
		<>
			{items.map((project) => (
				<div key={project.id} className="resume-entry">
					<div className="resume-project-title">
						{project.link && <Icon name="link" />}
						<strong>{typeset(project.name)}</strong>
						{project.technologies.length > 0 && (
							<>
								{" | "}
								<em>{typeset(project.technologies.join(", "))}</em>
							</>
						)}
					</div>
					<Bullets items={project.bullet_points} />
				</div>
			))}
		</>
	);
}

function Educations({ items }: { items: Education[] }) {
	return (
		<>
			{items.map((education) => (
				<div key={education.id} className="resume-entry">
					<Subheading
						title={education.name}
						right={education.duration}
						subtitle={education.subheading}
						subRight={education.location}
					/>
				</div>
			))}
		</>
	);
}

function Block({ block }: { block: SectionBlock }) {
	switch (block.type) {
		case "skill":
			return <Skills items={block.items} />;
		case "experience":
			return <Experiences items={block.items} />;
		case "project":
			return <Projects items={block.items} />;
		case "education":
			return <Educations items={block.items} />;
	}
}

export function ResumePreview({ document }: { document: ResumeDocument }) {
	return (
		<article className="resume-page">
			<Header fullName={document.full_name} info={document.personal_info} />

			{document.sections
				.filter((block) => block.items.length > 0)
				.map((block) => (
					<section
						className="resume-section"
						data-type={block.type}
						key={block.type}
					>
						<h2 className="resume-section-title">
							{SECTION_TITLES[block.type]}
						</h2>
						<Block block={block} />
					</section>
				))}
		</article>
	);
}
