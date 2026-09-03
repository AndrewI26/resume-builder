import { Button } from "@components/button";
import {
	FormError,
	sectionErrorMessage,
	TextInput,
} from "@components/section-form";
import { type ReactNode, useState } from "react";
import { useSearchParams } from "react-router";
import { useAuth } from "~/auth/auth-context";

export function meta() {
	return [{ title: "Profile · Resume Builder" }];
}

const dateFormatter = new Intl.DateTimeFormat("en-US", { dateStyle: "long" });

function formatJoinDate(createdAt: string): string {
	const date = new Date(createdAt);

	return Number.isNaN(date.getTime()) ? "—" : dateFormatter.format(date);
}

const GOOGLE_PROVIDER = "google";

/** What the callback can report back on the URL after a linking attempt. */
const LINK_ERROR_MESSAGES: Record<string, string> = {
	access_denied: "Google sign in was cancelled.",
	google_already_linked:
		"That Google account is already connected to another account here.",
	google_auth_failed: "Google could not verify that account. Try again.",
	google_not_configured: "Google sign in is not available on this server.",
	invalid_state: "That link attempt expired. Try again.",
	link_failed: "Could not connect Google. Try again.",
};

const rowClassName = "border-border border-b px-6 py-4 last:border-b-0";

function Field({
	action,
	label,
	value,
}: {
	action?: ReactNode;
	label: string;
	value: string;
}) {
	return (
		<div className={`flex items-center justify-between gap-4 ${rowClassName}`}>
			<span className="flex flex-col gap-1">
				<span className="text-ink-subtle text-sm">
					<span className="text-trim">{label}</span>
				</span>
				<span className="break-words text-ink text-lg">
					<span className="text-trim">{value}</span>
				</span>
			</span>
			{action}
		</div>
	);
}

/** The name row, which swaps between reading and editing in place.
 *
 * A blank submission is a deliberate way to clear the name — the API stores it
 * as null — so the input carries no required validation.
 */
function NameField({ name }: { name: string | null }) {
	const { updateProfile } = useAuth();
	const [editing, setEditing] = useState(false);
	const [draft, setDraft] = useState(name ?? "");
	const [error, setError] = useState<string | null>(null);
	const [saving, setSaving] = useState(false);

	const startEditing = () => {
		setDraft(name ?? "");
		setError(null);
		setEditing(true);
	};

	const save = async () => {
		setSaving(true);
		setError(null);

		try {
			await updateProfile({ name: draft });
			setEditing(false);
		} catch (caught) {
			setError(
				sectionErrorMessage(caught, "Could not save your name. Try again."),
			);
		} finally {
			setSaving(false);
		}
	};

	if (!editing) {
		return (
			<Field
				action={
					<Button onClick={startEditing} variant="tertiary">
						Edit
					</Button>
				}
				label="Name"
				value={name ?? "Not set"}
			/>
		);
	}

	return (
		<form
			className={`flex flex-col gap-3 ${rowClassName}`}
			noValidate
			onSubmit={(event) => {
				event.preventDefault();
				save();
			}}
		>
			<TextInput
				autoFocus
				autoComplete="name"
				disabled={saving}
				label="Name"
				maxLength={255}
				onChange={(event) => setDraft(event.target.value)}
				placeholder="Ada Lovelace"
				value={draft}
			/>

			{error !== null && <FormError>{error}</FormError>}

			<div className="flex items-center gap-3">
				<Button disabled={saving} type="submit">
					{saving ? "Saving…" : "Save"}
				</Button>
				<Button
					disabled={saving}
					onClick={() => setEditing(false)}
					variant="tertiary"
				>
					Cancel
				</Button>
			</div>
		</form>
	);
}

function SettingRow({
	action,
	description,
	title,
}: {
	action: ReactNode;
	description: string;
	title: string;
}) {
	return (
		<div className="flex flex-wrap items-center justify-between gap-4 rounded-card border border-border bg-card-secondary px-6 py-5">
			<span>
				<span className="block text-ink text-lg">
					<span className="text-trim">{title}</span>
				</span>
				<span className="mt-1 block text-ink-subtle leading-body">
					{description}
				</span>
			</span>
			{action}
		</div>
	);
}

/** Connecting and disconnecting Google.
 *
 * Connecting is a top level navigation rather than a fetch: the API owns the
 * handshake with Google and sends the browser back here afterwards, reporting
 * anything that went wrong as `?auth_error=`.
 */
function GoogleSignInMethod({ methods }: { methods: string[] }) {
	const [searchParams, setSearchParams] = useSearchParams();
	const [error, setError] = useState<string | null>(null);
	const [disconnecting, setDisconnecting] = useState(false);
	const { disconnectGoogle } = useAuth();

	const connected = methods.includes(GOOGLE_PROVIDER);
	// disconnecting the last method would lock the account out; the API refuses
	// it too, this just says so before the click
	const isOnlyMethod = connected && methods.length < 2;

	const authError = searchParams.get("auth_error");

	const dismissAuthError = () => {
		const next = new URLSearchParams(searchParams);
		next.delete("auth_error");
		setSearchParams(next, { replace: true });
	};

	const disconnect = async () => {
		setError(null);
		setDisconnecting(true);

		try {
			await disconnectGoogle();
			// whatever the last attempt reported no longer describes this row
			dismissAuthError();
		} catch (caught) {
			setError(
				sectionErrorMessage(caught, "Could not disconnect Google. Try again."),
			);
		} finally {
			setDisconnecting(false);
		}
	};

	return (
		<div className="flex flex-col gap-2">
			<SettingRow
				action={
					connected ? (
						<Button
							disabled={disconnecting || isOnlyMethod}
							onClick={disconnect}
							variant="tertiary"
						>
							{disconnecting ? "Disconnecting…" : "Disconnect"}
						</Button>
					) : (
						<Button
							onClick={() => {
								dismissAuthError();
								window.location.assign(
									`${import.meta.env.VITE_API_BASE_URL}/auth/google/link/start?next=/profile`,
								);
							}}
							variant="secondary"
						>
							Connect
						</Button>
					)
				}
				description={
					isOnlyMethod
						? "Connected. Set a password before disconnecting it."
						: connected
							? "Connected. You can sign in with Google."
							: "Sign in with your Google account as well as your password."
				}
				title="Google"
			/>

			{authError !== null && (
				<FormError>
					{LINK_ERROR_MESSAGES[authError] ?? LINK_ERROR_MESSAGES.link_failed}
				</FormError>
			)}
			{error !== null && <FormError>{error}</FormError>}
		</div>
	);
}

export default function Profile() {
	const { user } = useAuth();

	// RequireAuth holds the route until the session resolves, so `user` is set
	// by the time this renders.
	if (user === null) {
		return null;
	}

	return (
		<main className="mx-auto w-full max-w-3xl px-4 py-16">
			<h1 className="text-4xl leading-heading tracking-decreased">Profile</h1>
			<p className="mt-2 text-ink-subtle">Your account details and settings.</p>

			<div className="mt-8 rounded-card border border-border bg-card-secondary">
				<NameField name={user.name} />
				<Field label="Email" value={user.email} />
				<Field label="Member since" value={formatJoinDate(user.created_at)} />
			</div>

			<section className="mt-12">
				<h2 className="text-2xl leading-heading tracking-decreased">
					Sign-in methods
				</h2>
				<p className="mt-2 text-ink-subtle">How you get into this account.</p>

				<div className="mt-4 flex flex-col gap-4">
					<SettingRow
						action={
							<span className="text-ink-subtle">
								{user.sign_in_methods.includes("password") ? "Set" : "Not set"}
							</span>
						}
						description="Sign in with your email address and a password."
						title="Email and password"
					/>

					<GoogleSignInMethod methods={user.sign_in_methods} />
				</div>
			</section>

			<section className="mt-12">
				<h2 className="text-2xl leading-heading tracking-decreased">
					Account settings
				</h2>

				<div className="mt-4 flex flex-col gap-4">
					{/* No handler yet: the API has no password-reset endpoint. */}
					<SettingRow
						action={<Button variant="secondary">Reset password</Button>}
						description="Send yourself a link to choose a new password."
						title="Reset password"
					/>

					{/* No handler yet: the API has no account-deletion endpoint. */}
					<SettingRow
						action={<Button variant="danger">Delete account</Button>}
						description="Permanently remove your account, resumes and sections."
						title="Delete account"
					/>
				</div>
			</section>
		</main>
	);
}
