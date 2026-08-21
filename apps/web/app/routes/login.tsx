import { useForm } from "@tanstack/react-form";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { apiErrorMessage } from "~/api/errors";
import { useAuth } from "~/auth/auth-context";
import { TextField } from "~/auth/text-field";

export function meta() {
	return [
		{ title: "Sign in · Resume Builder" },
		{ name: "description", content: "Sign in to your resume." },
	];
}

export default function Login() {
	const { signIn, isAuthenticated, isLoading } = useAuth();
	const navigate = useNavigate();
	const [formError, setFormError] = useState<string | null>(null);

	useEffect(() => {
		if (!isLoading && isAuthenticated) {
			navigate("/dashboard", { replace: true });
		}
	}, [isLoading, isAuthenticated, navigate]);

	const form = useForm({
		defaultValues: { email: "", password: "" },
		onSubmit: async ({ value }) => {
			setFormError(null);
			try {
				await signIn(value);
				window.location.assign("/dashboard");
			} catch (error) {
				setFormError(
					apiErrorMessage(error, "Could not sign you in. Please try again."),
				);
			}
		},
	});

	return (
		<main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center px-4 py-16">
			<h1 className="text-4xl leading-heading tracking-decreased">Sign in</h1>
			<p className="mt-2 text-ink-subtle">Welcome back.</p>

			<form
				className="mt-8 flex flex-col gap-4"
				method="post"
				noValidate
				onSubmit={(event) => {
					event.preventDefault();
					form.handleSubmit();
				}}
			>
				<form.Field
					name="email"
					validators={{
						onBlur: ({ value }) =>
							/.+@.+\..+/.test(value)
								? undefined
								: "Enter a valid email address.",
					}}
				>
					{(field) => (
						<TextField
							autoComplete="username"
							error={field.state.meta.errors[0] ?? undefined}
							label="Email"
							name={field.name}
							onBlur={field.handleBlur}
							onChange={field.handleChange}
							placeholder="you@example.com"
							type="email"
							value={field.state.value}
						/>
					)}
				</form.Field>

				<form.Field
					name="password"
					validators={{
						onBlur: ({ value }) =>
							value.length > 0 ? undefined : "Enter your password.",
					}}
				>
					{(field) => (
						<TextField
							autoComplete="current-password"
							error={field.state.meta.errors[0] ?? undefined}
							label="Password"
							name={field.name}
							onBlur={field.handleBlur}
							onChange={field.handleChange}
							placeholder="••••••••"
							type="password"
							value={field.state.value}
						/>
					)}
				</form.Field>

				{formError && (
					<p
						className="rounded-xl bg-negative-bg px-4 py-2 text-sm text-negative"
						role="alert"
					>
						{formError}
					</p>
				)}

				<form.Subscribe
					selector={(state) => [state.canSubmit, state.isSubmitting] as const}
				>
					{([canSubmit, isSubmitting]) => (
						<button
							className="mt-1 rounded-button bg-btn-primary px-4 py-2 text-btn-primary-fg transition-opacity hover:opacity-90 disabled:bg-btn-primary-disabled disabled:text-btn-primary-disabled-fg"
							disabled={!canSubmit}
							type="submit"
						>
							{isSubmitting ? "Signing in…" : "Sign in"}
						</button>
					)}
				</form.Subscribe>
			</form>

			<p className="mt-8 text-sm text-ink-subtle">
				Don't have an account?{" "}
				<Link className="text-ink underline underline-offset-4" to="/signup">
					Create one
				</Link>
			</p>
		</main>
	);
}
