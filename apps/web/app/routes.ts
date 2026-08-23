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
		route("sections", "routes/sections.tsx"),
	]),
	route("*", "routes/not-found.tsx"),
] satisfies RouteConfig;
