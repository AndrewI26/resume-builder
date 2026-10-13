import { Button } from "@components/button";
import { useSearchParams } from "react-router";
import { apiBaseUrl } from "~/platform/host";

// what the API's Google redirect flow reports back as `?auth_error=`
const AUTH_ERROR_MESSAGES: Record<string, string> = {
	access_denied: "Google sign in was cancelled.",
	google_auth_failed: "Google could not verify that account. Try again.",
	google_not_configured: "Google sign in is not available on this server.",
	invalid_state: "That sign in attempt expired. Try again.",
};

const FALLBACK_MESSAGE = "Could not sign you in with Google. Try again.";

/** Why the last Google attempt failed, if it did. */
export function useGoogleAuthError(): string | null {
	const [searchParams] = useSearchParams();
	const authError = searchParams.get("auth_error");

	if (authError === null) {
		return null;
	}
	return AUTH_ERROR_MESSAGES[authError] ?? FALLBACK_MESSAGE;
}

function GoogleLogo() {
	return (
		<svg aria-hidden="true" className="size-4" viewBox="0 0 48 48">
			<path
				d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"
				fill="#FFC107"
			/>
			<path
				d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"
				fill="#FF3D00"
			/>
			<path
				d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"
				fill="#4CAF50"
			/>
			<path
				d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C36.9 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"
				fill="#1976D2"
			/>
		</svg>
	);
}

/**
 * Sign in, or sign up, with Google. A plain navigation to the API, which
 * bounces the browser through Google's consent screen and back to `next`
 * with the session cookie set. Google makes the account on first use, so
 * the sign in and sign up pages share this.
 */
export function GoogleSignInButton({ next = "/dashboard" }: { next?: string }) {
	return (
		<Button
			className="w-full"
			icon={<GoogleLogo />}
			onClick={() => {
				window.location.assign(
					`${apiBaseUrl}/auth/google/login?${new URLSearchParams({ next })}`,
				);
			}}
			variant="secondary"
		>
			Continue with Google
		</Button>
	);
}

/** The rule between the Google button and the email form. */
export function OrDivider() {
	return (
		<div className="my-6 flex items-center gap-3 text-sm text-ink-subtle">
			<span className="h-px flex-1 bg-border" />
			or
			<span className="h-px flex-1 bg-border" />
		</div>
	);
}
