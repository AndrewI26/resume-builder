/**
 * The made-up library behind the landing page's demos.
 *
 * Shaped like the app's own model, cut down to what a miniature page can
 * show: a library of entries, and resumes that hold references into it rather
 * than copies — which is the whole point the demos are making.
 */

export type DemoType = "experience" | "project" | "education" | "skill";

export interface DemoEntry {
	id: string;
	type: DemoType;
	title: string;
	/** The organisation, the stack or the degree: whatever sits beside the title. */
	subtitle: string;
	dates?: string;
	bullets: string[];
}

export interface DemoVersion {
	id: string;
	name: string;
	/** Which headings print, top to bottom. */
	order: DemoType[];
	/** Which library entries are attached, in the order they print. */
	entries: string[];
}

export const DEMO_TITLES: Record<DemoType, string> = {
	experience: "Experience",
	project: "Projects",
	education: "Education",
	skill: "Skills",
};

export const DEMO_LIBRARY: DemoEntry[] = [
	{
		id: "lumen",
		type: "experience",
		title: "Frontend Developer",
		subtitle: "Lumen Health",
		dates: "2023 – Present",
		bullets: [
			"Rebuilt the patient portal in React, cutting load time by 40%",
			"Led the move to a shared design system across four teams",
		],
	},
	{
		id: "brightline",
		type: "experience",
		title: "Platform Engineer",
		subtitle: "Brightline",
		dates: "2021 – 2023",
		bullets: [
			"Moved CI to ephemeral runners, halving median build time",
			"Ran the on-call rotation for twelve production services",
		],
	},
	{
		id: "northwind",
		type: "experience",
		title: "Software Engineer Intern",
		subtitle: "Northwind Logistics",
		dates: "2020",
		bullets: ["Built a route-planning API serving two million requests a day"],
	},
	{
		id: "transit",
		type: "project",
		title: "Transit Map",
		subtitle: "TypeScript, D3",
		bullets: ["A live map of every bus in the city, updated each second"],
	},
	{
		id: "streamlens",
		type: "project",
		title: "Stream Lens",
		subtitle: "Go, Kafka",
		bullets: ["An inspector for event streams, used by three teams"],
	},
	{
		id: "waterloo",
		type: "education",
		title: "University of Waterloo",
		subtitle: "BSc, Computer Science",
		dates: "2016 – 2021",
		bullets: [],
	},
	{
		id: "skills-web",
		type: "skill",
		title: "Frontend",
		subtitle: "React, TypeScript, CSS, Accessibility",
		bullets: [],
	},
	{
		id: "skills-infra",
		type: "skill",
		title: "Infrastructure",
		subtitle: "Go, Docker, Postgres, AWS",
		bullets: [],
	},
];

export const DEMO_VERSIONS: DemoVersion[] = [
	{
		id: "frontend",
		name: "Frontend",
		order: ["experience", "project", "skill", "education"],
		entries: ["lumen", "brightline", "transit", "skills-web", "waterloo"],
	},
	{
		id: "platform",
		name: "Platform",
		order: ["experience", "skill", "project", "education"],
		entries: ["brightline", "lumen", "streamlens", "skills-infra", "waterloo"],
	},
	{
		id: "new-grad",
		name: "New grad",
		order: ["education", "project", "experience", "skill"],
		entries: [
			"waterloo",
			"transit",
			"streamlens",
			"northwind",
			"skills-web",
			"skills-infra",
		],
	},
];

export const DEMO_NAME = "Alex Rivera";
export const DEMO_CONTACT = "alex@rivera.dev · github.com/arivera · Toronto";
