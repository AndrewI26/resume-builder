/**
 * The shape of `GET /resumes/{id}/document`.
 *
 * Aliased from the generated OpenAPI client rather than written out by hand,
 * so the API is the single source of truth. If the endpoint's shape changes,
 * `bun run codegen` propagates it and anything here that no longer fits stops
 * compiling — which is the point.
 */

// the same specifier the generated client uses: importing it any other way
// makes TypeScript treat it as a second, unrelated copy of these types
import type { components } from "@api/schema.d.ts";

type Schemas = components["schemas"];

export type SectionType = Schemas["ResumeSectionType"];

/**
 * A line of resume text plus the runs of it that render bold.
 *
 * Each range in `bolded` is a pair of **inclusive** character indices into
 * `text`: `[0, 6]` over `"Shipped it"` covers `"Shipped"`.
 *
 * The pair is typed as `number[]` rather than `[number, number]` on purpose.
 * `openapi-react-query` widens tuples when it infers a response type, so a
 * document straight off the client will not satisfy the stricter form. The
 * API validates the pairs, and `splitBullet` ignores any range that does not
 * come through as a usable one.
 */
export interface BulletPoint {
	text: string;
	bolded: number[][];
}

export type PersonalInfo = Schemas["PersonalInfoRead"];
export type Education = Schemas["EducationRead"];
export type Skill = Schemas["SkillRead"];

export type Experience = Omit<Schemas["ExpirenceRead"], "bullet_points"> & {
	bullet_points: BulletPoint[];
};

export type Project = Omit<Schemas["ProjectRead"], "bullet_points"> & {
	bullet_points: BulletPoint[];
};

export type SectionBlock =
	| { type: "education"; items: Education[] }
	| { type: "experience"; items: Experience[] }
	| { type: "project"; items: Project[] }
	| { type: "skill"; items: Skill[] };

export type ResumeDocument = Omit<Schemas["ResumeDocument"], "sections"> & {
	sections: SectionBlock[];
};
