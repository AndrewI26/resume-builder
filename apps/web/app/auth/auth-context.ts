import type { components } from "@api/schema.d.ts";
import { createContext, useContext } from "react";

export type UserRead = components["schemas"]["UserRead"];
type UserCreate = components["schemas"]["UserCreate"];
type UserLogin = components["schemas"]["UserLogin"];

export type AuthContextValue = {
	user: UserRead | null;
	isAuthenticated: boolean;
	isLoading: boolean;
	signIn: (credentials: UserLogin) => Promise<UserRead>;
	signUp: (credentials: UserCreate) => Promise<UserRead>;
	signInWithGoogle: (credential: string) => Promise<UserRead>;
	signOut: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
	const context = useContext(AuthContext);

	if (context === null) {
		throw new Error("useAuth must be used within an AuthProvider");
	}

	return context;
}
