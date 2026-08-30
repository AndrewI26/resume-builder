import {
	index,
	layout,
	type RouteConfig,
	route,
} from "@react-router/dev/routes";

export default [
	index("routes/home.tsx"),
	route("login", "routes/login.tsx"),
	route("signup", "routes/signup.tsx"),
	layout("auth/protected-layout.tsx", [
		route("dashboard", "routes/dashboard.tsx"),
		route("resumes", "routes/resumes.tsx"),
		route("resumes/:resumeId", "routes/resume.$resumeId.tsx"),
		route("sections", "routes/sections.tsx"),
		route("sections/education/new", "routes/sections.education.tsx", {
			id: "routes/sections.education.new",
		}),
		route("sections/education/:educationId", "routes/sections.education.tsx"),
		route("sections/experience/new", "routes/sections.experience.tsx", {
			id: "routes/sections.experience.new",
		}),
		route(
			"sections/experience/:experienceId",
			"routes/sections.experience.tsx",
		),
		route("sections/personal-info/new", "routes/sections.personal-info.tsx", {
			id: "routes/sections.personal-info.new",
		}),
		route(
			"sections/personal-info/:personalInfoId",
			"routes/sections.personal-info.tsx",
		),
		route("sections/project/new", "routes/sections.project.tsx", {
			id: "routes/sections.project.new",
		}),
		route("sections/project/:projectId", "routes/sections.project.tsx"),
		route("sections/skill/new", "routes/sections.skill.tsx", {
			id: "routes/sections.skill.new",
		}),
		route("sections/skill/:skillId", "routes/sections.skill.tsx"),
	]),
	route("*", "routes/not-found.tsx"),
] satisfies RouteConfig;
