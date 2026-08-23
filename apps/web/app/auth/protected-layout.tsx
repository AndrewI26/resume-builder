import { Outlet } from "react-router";
import { RequireAuth } from "./require-auth";

export default function ProtectedLayout() {
	return (
		<RequireAuth>
			<Outlet />
		</RequireAuth>
	);
}
