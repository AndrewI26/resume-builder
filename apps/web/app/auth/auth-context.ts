import { createContext, useContext } from "react";
import type { UserCreate, UserLogin, UserRead } from "~/api/generated/model";

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
