import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback, useMemo } from "react";
import { $api } from "@api/api";
import {
	AuthContext,
	type AuthContextValue,
	type UserRead,
} from "./auth-context";

export function AuthProvider({ children }: { children: ReactNode }) {
	const queryClient = useQueryClient();

	const session = $api.useQuery("get", "/auth/me", undefined, { retry: false });

	const { mutateAsync: loginRequest } = $api.useMutation("post", "/auth/login");
	const { mutateAsync: registerRequest } = $api.useMutation(
		"post",
		"/auth/register",
	);
	const { mutateAsync: googleTokenRequest } = $api.useMutation(
		"post",
		"/auth/google/token",
	);
	const { mutateAsync: logoutRequest } = $api.useMutation(
		"post",
		"/auth/logout",
	);

	const cacheUser = useCallback(
		(user: UserRead) => {
			queryClient.setQueryData(
				$api.queryOptions("get", "/auth/me").queryKey,
				user,
			);
			return user;
		},
		[queryClient],
	);

	const signIn = useCallback(
		async (credentials: { email: string; password: string }) => {
			const user = await loginRequest({ body: credentials });
			return cacheUser(user);
		},
		[loginRequest, cacheUser],
	);

	const signUp = useCallback(
		async (credentials: { email: string; password: string }) => {
			const user = await registerRequest({ body: credentials });
			return cacheUser(user);
		},
		[registerRequest, cacheUser],
	);

	const signInWithGoogle = useCallback(
		async (credential: string) => {
			const user = await googleTokenRequest({ body: { credential } });
			return cacheUser(user);
		},
		[googleTokenRequest, cacheUser],
	);

	const signOut = useCallback(async () => {
		await logoutRequest({});
		queryClient.clear();
	}, [logoutRequest, queryClient]);

	const user = session.data ?? null;

	const value = useMemo<AuthContextValue>(
		() => ({
			user,
			isAuthenticated: user !== null,
			isLoading: session.isPending,
			signIn,
			signUp,
			signInWithGoogle,
			signOut,
		}),
		[user, session.isPending, signIn, signUp, signInWithGoogle, signOut],
	);

	return <AuthContext value={value}>{children}</AuthContext>;
}
