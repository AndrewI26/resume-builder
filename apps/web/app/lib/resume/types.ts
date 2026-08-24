/**
 * The shape of `GET /resume/{id}/document`.
 *
 * Mirrors `schemas/resume.py` on the API. Blocks arrive in the resume's
 * section order with bullet points already hydrated, so a renderer can walk
 * this structure without sorting or fetching anything further.
 */

export type SectionType = "education" | "experience" | "project" | "skill";

export interface BulletPoint {
	text: string;
	/**
	 * Character ranges of `text` that render bold, each **inclusive** on both
	 * ends: `[0, 6]` over `"Shipped it"` covers `"Shipped"`. The API guarantees
	 * they arrive sorted and non-overlapping.
	 */
	bolded: [number, number][];
}

export interface PersonalInfo {
	email: string | null;
	phone_number: string | null;
	address: string | null;
	github: string | null;
	linkedin: string | null;
	portfolio: string | null;
}

export interface Education {
	id: string;
	name: string;
	subheading: string;
	duration: string;
	location: string;
}

export interface Experience {
	id: string;
	company: string;
	position: string;
	duration: string;
	location: string;
	bullet_points: BulletPoint[];
}

export interface Project {
	id: string;
	name: string;
	link: string | null;
	technologies: string[];
	bullet_points: BulletPoint[];
}

export interface Skill {
	id: string;
	name: string;
	items: string[];
	position: number;
}

export type SectionBlock =
	| { type: "education"; items: Education[] }
	| { type: "experience"; items: Experience[] }
	| { type: "project"; items: Project[] }
	| { type: "skill"; items: Skill[] };

export interface ResumeDocument {
	id: string;
	title: string;
	template: string;
	/** Already resolved against the account name; empty when neither is set. */
	full_name: string;
	personal_info: PersonalInfo | null;
	sections: SectionBlock[];
}
