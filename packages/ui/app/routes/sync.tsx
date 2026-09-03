/**
 * Keeping this machine's library and an account in step.
 *
 * Only reachable in the desktop app: the browser's data is already the
 * account, so there is nothing here for it to reconcile with.
 *
 * The screen's real job is the conflicts. Everything else — connecting,
 * running a sync — is a button and a status line, but a conflict is a question
 * the app cannot answer on its own, and the answer is somebody's work either
 * way. So both versions are shown in full and neither is preferred by the
 * layout.
 */

import { $api } from "@api/api";
import { Button } from "@components/button";
import { FormError, TextInput } from "@components/section-form";
import { useState } from "react";
import { useNavigate } from "react-router";
import { canSync } from "~/platform/host";

export function meta() {
	return [{ title: "Sync · Resume Builder" }];
}

/** The account this build talks to. */
const DEFAULT_ACCOUNT_URL =
	import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const SECTION_LABELS: Record<string, string> = {
	education: "Education",
	experience: "Experience",
	personal_info: "Contact details",
	project: "Project",
	resume: "Resume",
	skill: "Skills",
};

/**
 * A one-line description of a record, whatever kind it is.
 *
 * The snapshot is the record's own API shape, so there is no single field to
 * read; this picks whichever names the thing to a person.
 */
function describe(snapshot: Record<string, unknown>): string {
	for (const key of ["title", "name", "company", "email"]) {
		const value = snapshot[key];
		if (typeof value === "string" && value.length > 0) {
			return value;
		}
	}

	return "Untitled";
}

/**
 * The fields worth showing, without the bookkeeping.
 *
 * Sorted, because the two versions are read side by side and the snapshots do
 * not agree on key order — one arrived from the account's JSON and the other
 * was written here. Unsorted, the same field sits on a different line in each
 * column and the comparison has to be done by hunting rather than by looking.
 */
function summarise(snapshot: Record<string, unknown>): [string, string][] {
	return Object.entries(snapshot)
		.filter(([key]) => key !== "id" && key !== "updated_at")
		.sort(([left], [right]) => left.localeCompare(right))
		.map(([key, value]) => [
			key.replaceAll("_", " "),
			typeof value === "string" ? value : JSON.stringify(value),
		]);
}

function Side({
	choose,
	choosing,
	label,
	snapshot,
	version,
}: {
	choose: () => void;
	choosing: boolean;
	label: string;
	snapshot: Record<string, unknown>;
	version: number;
}) {
	return (
		<div className="flex min-w-0 flex-1 flex-col gap-3 rounded-xl border border-border p-4">
			<div className="flex items-baseline justify-between gap-3">
				<h4 className="font-semibold text-ink">{label}</h4>
				<span className="text-ink-subtle text-xs">version {version}</span>
			</div>

			<dl className="flex flex-col gap-1 text-sm">
				{summarise(snapshot).map(([key, value]) => (
					<div className="flex gap-2" key={key}>
						<dt className="shrink-0 text-ink-subtle capitalize">{key}</dt>
						<dd className="min-w-0 break-words text-ink">{value}</dd>
					</div>
				))}
			</dl>

			<Button disabled={choosing} onClick={choose} variant="secondary">
				Keep this one
			</Button>
		</div>
	);
}

export default function Sync() {
	const navigate = useNavigate();
	const [accountUrl, setAccountUrl] = useState(DEFAULT_ACCOUNT_URL);
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [lastRun, setLastRun] = useState<string | null>(null);

	const status = $api.useQuery("get", "/sync/status", undefined, {
		enabled: canSync,
		retry: false,
	});

	const { mutateAsync: connect, isPending: connecting } = $api.useMutation(
		"post",
		"/sync/connect",
	);
	const { mutateAsync: disconnect } = $api.useMutation(
		"post",
		"/sync/disconnect",
	);
	const { mutateAsync: run, isPending: running } = $api.useMutation(
		"post",
		"/sync/run",
	);
	const { mutateAsync: resolve, isPending: resolving } = $api.useMutation(
		"post",
		"/sync/conflicts/{record_id}/resolve",
	);

	// the browser build has no library of its own to reconcile, and saying so
	// is better than a screen whose buttons cannot do anything
	if (!canSync) {
		return (
			<main className="mx-auto flex w-full max-w-2xl flex-col gap-4 px-6 py-16">
				<h1 className="font-semibold text-2xl text-ink">Sync</h1>
				<p className="text-ink-subtle">
					You are already signed in to your account here, so there is nothing to
					sync. This is for the desktop app, which keeps a copy of your library
					on your own machine.
				</p>
				<Button onClick={() => navigate("/dashboard")} variant="secondary">
					Back to dashboard
				</Button>
			</main>
		);
	}

	const state = status.data;
	const conflicts = state?.conflicts ?? [];

	async function attempt(action: () => Promise<unknown>) {
		setError(null);
		try {
			await action();
			await status.refetch();
		} catch (failure) {
			setError(
				failure instanceof Error
					? failure.message
					: "That did not work. Try again.",
			);
		}
	}

	return (
		<main className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-6 py-12">
			<header className="flex flex-col gap-2">
				<h1 className="font-semibold text-2xl text-ink">Sync</h1>
				<p className="text-ink-subtle">
					Your library lives on this machine and works without an account.
					Connect one to keep it in step with the web app and your other
					computers.
				</p>
			</header>

			{error && <FormError>{error}</FormError>}

			{state?.connected ? (
				<section className="flex flex-col gap-4 rounded-xl border border-border p-6">
					<div className="flex flex-wrap items-center justify-between gap-3">
						<div className="flex flex-col gap-1">
							<span className="text-ink-subtle text-sm">Connected to</span>
							<span className="text-ink text-lg">{state.account_email}</span>
						</div>

						<div className="flex gap-3">
							<Button
								disabled={running}
								onClick={() =>
									attempt(async () => {
										const report = await run({});
										setLastRun(
											`Received ${report.pulled}, sent ${report.pushed}` +
												(report.conflicts.length > 0
													? `, ${report.conflicts.length} need you`
													: ""),
										);
									})
								}
							>
								{running ? "Syncing…" : "Sync now"}
							</Button>

							<Button
								onClick={() => attempt(() => disconnect({}))}
								variant="tertiary"
							>
								Disconnect
							</Button>
						</div>
					</div>

					{lastRun && <p className="text-ink-subtle text-sm">{lastRun}</p>}
				</section>
			) : (
				<section className="flex flex-col gap-4 rounded-xl border border-border p-6">
					<h2 className="font-semibold text-ink text-lg">Connect an account</h2>
					<p className="text-ink-subtle text-sm">
						Nothing is sent until you connect. Everything already here is
						uploaded on the first sync.
					</p>

					<TextInput
						label="Account address"
						onChange={(event) => setAccountUrl(event.target.value)}
						value={accountUrl}
					/>
					<TextInput
						label="Email"
						onChange={(event) => setEmail(event.target.value)}
						type="email"
						value={email}
					/>
					<TextInput
						label="Password"
						onChange={(event) => setPassword(event.target.value)}
						type="password"
						value={password}
					/>

					<Button
						disabled={connecting || email === "" || password === ""}
						onClick={() =>
							attempt(() =>
								connect({
									body: { base_url: accountUrl, email, password },
								}),
							)
						}
					>
						{connecting ? "Connecting…" : "Connect"}
					</Button>
				</section>
			)}

			{conflicts.length > 0 && (
				<section className="flex flex-col gap-4">
					<div className="flex flex-col gap-1">
						<h2 className="font-semibold text-ink text-lg">
							{conflicts.length === 1
								? "One thing needs you"
								: `${conflicts.length} things need you`}
						</h2>
						<p className="text-ink-subtle text-sm">
							These were changed both here and elsewhere. Nothing has been
							overwritten — choose which version to keep and the next sync will
							carry it out.
						</p>
					</div>

					{conflicts.map((conflict) => {
						const mine = conflict.local_snapshot as Record<string, unknown>;
						const theirs = conflict.cloud_snapshot as Record<string, unknown>;

						return (
							<article
								className="flex flex-col gap-4 rounded-xl border border-border p-6"
								key={conflict.record_id}
							>
								<div className="flex flex-col gap-1">
									<span className="text-ink-subtle text-sm">
										{SECTION_LABELS[conflict.record_type] ??
											conflict.record_type}
									</span>
									<h3 className="font-semibold text-ink">{describe(mine)}</h3>
								</div>

								<div className="flex flex-col gap-4 md:flex-row">
									<Side
										choose={() =>
											attempt(() =>
												resolve({
													body: { choice: "mine" },
													params: { path: { record_id: conflict.record_id } },
												}),
											)
										}
										choosing={resolving}
										label="On this computer"
										snapshot={mine}
										version={conflict.local_version}
									/>
									<Side
										choose={() =>
											attempt(() =>
												resolve({
													body: { choice: "theirs" },
													params: { path: { record_id: conflict.record_id } },
												}),
											)
										}
										choosing={resolving}
										label="In your account"
										snapshot={theirs}
										version={conflict.cloud_version}
									/>
								</div>
							</article>
						);
					})}
				</section>
			)}
		</main>
	);
}
