import { type ReactNode, useEffect } from "react";
import { useNavigate } from "react-router";
import { useAuth } from "./auth-context";

export function RequireAuth({ children }: { children: ReactNode }) {
	const { isAuthenticated, isLoading } = useAuth();
	const navigate = useNavigate();

	useEffect(() => {
		if (!isLoading && !isAuthenticated) {
			navigate("/login", { replace: true });
		}
	}, [isLoading, isAuthenticated, navigate]);

	if (isLoading || !isAuthenticated) return null;

	return <>{children}</>;
}
