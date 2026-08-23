import { index, type RouteConfig, route } from "@react-router/dev/routes";

export default [
	index("routes/home.tsx"),
	route("login", "routes/login.tsx"),
	route("signup", "routes/signup.tsx"),
	route("dashboard", "routes/dashboard.tsx"),
	route("*", "routes/not-found.tsx"),
] satisfies RouteConfig;
