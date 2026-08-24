/**
 * The resume from `resume.tex` at the repo root, expressed as a
 * `ResumeDocument`.
 *
 * Used as the golden-file input, so the generated output can be read next to
 * the hand-written original. It is not a byte-for-byte match: the original
 * carries things the data model has no column for — a link on an employer,
 * the two-column awards block under the high school entry — and those are
 * absent here rather than faked.
 */

import type { ResumeDocument } from "../../resume/types";

const plain = (text: string) => ({ text, bolded: [] as [number, number][] });

/** Bold every listed substring, resolved to inclusive offsets. */
const bold = (text: string, ...phrases: string[]) => ({
	text,
	bolded: phrases
		.map((phrase): [number, number] => {
			const start = text.indexOf(phrase);
			if (start === -1) throw new Error(`"${phrase}" is not in the text`);
			return [start, start + phrase.length - 1];
		})
		.sort((a, b) => a[0] - b[0]),
});

export const SAMPLE_DOCUMENT: ResumeDocument = {
	id: "00000000-0000-0000-0000-000000000001",
	title: "Software Engineer",
	template: "jakes",
	full_name: "Andrew Iammancini",
	personal_info: {
		email: "andrewi44@icloud.com",
		phone_number: null,
		address: null,
		github: "https://github.com/AndrewI26",
		linkedin: "https://linkedin.com/in/andrew-iammancini",
		portfolio: "https://andrewi.vercel.app",
	},
	sections: [
		{
			type: "skill",
			items: [
				{
					id: "10000000-0000-0000-0000-000000000001",
					name: "Languages",
					position: 0,
					items: [
						"TypeScript/JavaScript",
						"Python",
						"Go",
						"C",
						"C++",
						"Racket",
						"Haskell",
						"SQL",
						"HTML/CSS",
					],
				},
				{
					id: "10000000-0000-0000-0000-000000000002",
					name: "Technologies/Frameworks",
					position: 1,
					items: [
						"React",
						"Next.js",
						"React Router",
						"Vite",
						"React Native",
						"Expo",
						"Fast API",
						"Django",
						"Express.js",
						"MongoDB",
						"Selenium",
						"Postgres",
						"Docker",
						"Tailwind",
					],
				},
			],
		},
		{
			type: "experience",
			items: [
				{
					id: "20000000-0000-0000-0000-000000000001",
					company: "Eon Media",
					position: "Full-stack Developer",
					duration: "May 2026 -- August 2026",
					location: "Remote",
					bullet_points: [
						plain(
							"Incoming summer 2026. Planning to work on full-stack solutions for video editing software!",
						),
					],
				},
				{
					id: "20000000-0000-0000-0000-000000000002",
					company: "PROVA Innovations",
					position: "Full-stack Developer",
					duration: "May 2025 -- August 2025",
					location: "Hamilton, Ontario",
					bullet_points: [
						bold(
							"Lead developer of a clinician portal for tracking patients activity using PROVA's electronic insoles, built with React Router and Vite. Expanded the backend API using FastAPI, to support new clinician portal functionality.",
							"React Router",
							"Vite",
							"FastAPI",
						),
						plain(
							"Implemented core features like viewing patients goals, training adherence, and building custom reports and surveys with drag and drop widgets.",
						),
						bold(
							"Constructed a demo for 100+ investors by adding a live insole pressure heatmap and a live walking animation to the mobile app using React Native, to showcase insole accuracy.",
							"100+",
							"insole pressure heatmap",
							"walking animation",
							"React Native",
						),
						plain(
							"Collaborated with leadership to design and propose a full rewrite of the company's API backend, improving scalability for future gait metrics, and incorporating the clinician web portal I designed.",
						),
					],
				},
				{
					id: "20000000-0000-0000-0000-000000000003",
					company: "Formula Electric",
					position: "Software Developer",
					duration: "September 2024 -- August 2025",
					location: "Hamilton, Ontario",
					bullet_points: [
						bold(
							"Collaborated with over 30 developers to maintain software for an electric Formula One car.",
							"30",
						),
						bold(
							"Migrated software in the loop system from a gRPC communication architecture to a TCP based system.",
							"software in the loop",
							"gRPC",
							"TCP",
						),
						bold(
							"Used TCP web sockets to simulate input to the racecar's firmware, verifying output accuracy under simulated conditions.",
							"TCP web sockets",
						),
					],
				},
			],
		},
		{
			type: "project",
			items: [
				{
					id: "30000000-0000-0000-0000-000000000001",
					name: "CampusCart",
					link: null,
					technologies: [
						"React Router",
						"Vite",
						"Express.js",
						"Postgres",
						"Docker",
						"AWS",
					],
					bullet_points: [
						bold(
							"Founder of a full-stack website that connects UW students who are looking to exchange rentals, textbooks and other miscellaneous items.",
							"Founder",
						),
						bold(
							"Handled 1000 monthly visitors and 30+ listings by deploying remotely to an AWS EC2 instance with Docker.",
							"1000",
							"30+",
							"AWS EC2",
							"Docker",
						),
					],
				},
				{
					id: "30000000-0000-0000-0000-000000000002",
					name: "Whiz Backend Framework",
					link: "https://github.com/AndrewI26/whiz",
					technologies: ["Go"],
					bullet_points: [
						bold(
							"Built a minimal backend framework, similar to Express.js or Flask, using Go.",
							"Go",
						),
						bold(
							"Implemented a custom router, server and logger, which supports custom route handlers, dynamic paths, and automatic traffic logging.",
							"router",
							"server",
							"logger",
						),
					],
				},
				{
					id: "30000000-0000-0000-0000-000000000003",
					name: "McMaster Trivia",
					link: null,
					technologies: ["Next.js", "Vercel"],
					bullet_points: [
						bold(
							"Developed, and deployed a viral quiz game designed for McMaster students, built with Next.js and Neon as a serverless Postgres database.",
							"Next.js",
							"Neon",
							"Postgres",
						),
						bold(
							"Handled request for 4000 users across 4 days by implementing robust analytics and logging.",
							"4000 users",
							"4 days",
						),
					],
				},
				{
					id: "30000000-0000-0000-0000-000000000004",
					name: "Keybindings Cheatsheet",
					link: "https://marketplace.visualstudio.com/items?itemName=andrewi.keybindings-cheatsheet",
					technologies: ["Typescript", "Handlebars", "esbuild"],
					bullet_points: [
						bold(
							"Garnered 15+ installs with a custom VS Code extension that parses a users configured keybindings file and dynamically generate HTML with Handlebars.",
							"15+ installs",
							"HTML",
							"Handlebars",
						),
					],
				},
				{
					id: "30000000-0000-0000-0000-000000000005",
					name: "Brain-rot Clips Generator",
					link: "https://github.com/AndrewI26/Youtube-Shorts-Creator",
					technologies: ["Django", "React", "Next.js"],
					bullet_points: [
						bold(
							"Developed a full-stack website to create YouTube Shorts using a Reddit post.",
							"full-stack",
						),
						plain(
							"Generated YouTube shorts followed the same format of an automated voice reading a Reddit post with Subway Surfers video in the background.",
						),
					],
				},
			],
		},
		{
			type: "education",
			items: [
				{
					id: "40000000-0000-0000-0000-000000000001",
					name: "University of Waterloo",
					subheading: "Computer Science (B.A.Sc.) - 3.98/4.00 GPA (90.8% CAV)",
					duration: "September 2025 - present",
					location: "Waterloo, Ontario",
				},
				{
					id: "40000000-0000-0000-0000-000000000002",
					name: "McMaster University",
					subheading:
						"Computer Science (B.A.Sc.) - 4.00/4.00 GPA (completed first year then transferred)",
					duration: "September 2024 - May 2025",
					location: "Hamilton, Ontario",
				},
				{
					id: "40000000-0000-0000-0000-000000000003",
					name: "St. Peters High school",
					subheading: "High School - Grade 12 CAV of 99.0%",
					duration: "September 2020 -- June 2024",
					location: "Peterborough, Ontario",
				},
			],
		},
	],
};
