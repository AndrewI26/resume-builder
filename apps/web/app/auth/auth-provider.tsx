import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback, useMemo } from "react";
import {
	getMeQueryKey,
	type meResponse,
	useGoogleToken,
	useLogin,
	useLogout,
	useMe,
	useRegister,
} from "~/api/generated/endpoints/auth/auth";
import type { UserCreate, UserLogin, UserRead } from "~/api/generated/model";
import { ApiError } from "~/api/fetcher";
import { AuthContext, type AuthContextValue } from "./auth-context";

export function AuthProvider({ children }: { children: ReactNode }) {
	const queryClient = useQueryClient();

	const session = useMe<meResponse, ApiError>({
		query: { retry: false },
	});

	const { mutateAsync: loginRequest } = useLogin();
	const { mutateAsync: registerRequest } = useRegister();
	const { mutateAsync: googleTokenRequest } = useGoogleToken();
	const { mutateAsync: logoutRequest } = useLogout();

	const cacheUser = useCallback(
		(user: UserRead, headers: Headers) => {
			queryClient.setQueryData<meResponse>(getMeQueryKey(), {
				status: 200,
				data: user,
				headers,
			});
			return user;
		},
		[queryClient],
	);

	const signIn = useCallback(
		async (credentials: UserLogin) => {
			const response = await loginRequest({ data: credentials });

			if (response.status !== 200) {
				throw new ApiError(response.status, response.data);
			}

			return cacheUser(response.data, response.headers);
		},
		[loginRequest, cacheUser],
	);

	const signUp = useCallback(
		async (credentials: UserCreate) => {
			const response = await registerRequest({ data: credentials });

			if (response.status !== 201) {
				throw new ApiError(response.status, response.data);
			}

			return cacheUser(response.data, response.headers);
		},
		[registerRequest, cacheUser],
	);

	const signInWithGoogle = useCallback(
		async (credential: string) => {
			const response = await googleTokenRequest({ data: { credential } });

			if (response.status !== 200) {
				throw new ApiError(response.status, response.data);
			}

			return cacheUser(response.data, response.headers);
		},
		[googleTokenRequest, cacheUser],
	);

	const signOut = useCallback(async () => {
		await logoutRequest();
		queryClient.clear();
	}, [logoutRequest, queryClient]);

	const user = session.data?.status === 200 ? session.data.data : null;

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
