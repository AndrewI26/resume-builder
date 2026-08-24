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
import { typeset } from "~/lib/resume/typography";
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

const SECTION_TITLES = {
	education: "Education",
	experience: "Experience",
	project: "Projects",
	skill: "Skills",
} as const;

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
			<div className="resume-row">
				<span className="font-bold">{typeset(title)}</span>
				<span className="font-bold">{typeset(right)}</span>
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
			<span className="underline">{typeset(label)}</span>
		</span>
	);
}

/** Generic glyphs standing in for the template's fontawesome icons. */
function Icon({ name }: { name: string }) {
	const paths: Record<string, string> = {
		envelope: "M2 4h12v8H2z M2 4l6 4 6-4",
		link: "M6 10a3 3 0 0 0 4 0l3-3a3 3 0 0 0-4-4L8 4 M10 6a3 3 0 0 0-4 0L3 9a3 3 0 0 0 4 4l1-1",
		globe:
			"M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1z M1 8h14 M8 1c4 4 4 10 0 14 M8 1C4 5 4 11 8 15",
		phone:
			"M3 2h3l1 4-2 1a9 9 0 0 0 4 4l1-2 4 1v3a1 1 0 0 1-1 1A12 12 0 0 1 2 3a1 1 0 0 1 1-1z",
		pin: "M8 1a4 4 0 0 0-4 4c0 3 4 9 4 9s4-6 4-9a4 4 0 0 0-4-4z M8 5.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z",
	};

	return (
		<svg
			viewBox="0 0 16 16"
			className="resume-icon"
			fill="none"
			stroke="currentColor"
			strokeWidth="1.2"
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
		entries.push({ icon: "link", label: displayUrl(info.linkedin) });
	}
	if (info?.github) {
		entries.push({ icon: "link", label: displayUrl(info.github) });
	}
	if (info?.portfolio) entries.push({ icon: "globe", label: "Portfolio" });
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
					<section key={block.type} className="resume-section">
						<h2 className="resume-section-title">
							{SECTION_TITLES[block.type]}
						</h2>
						<Block block={block} />
					</section>
				))}
		</article>
	);
}
