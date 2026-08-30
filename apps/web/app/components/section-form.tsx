import type { components } from "@api/schema.d.ts";
import { Button } from "@components/button";
import { type InputHTMLAttributes, type ReactNode, useId } from "react";
import { Link } from "react-router";

type SectionError =
	| components["schemas"]["ErrorDetail"]
	| components["schemas"]["HTTPValidationError"];

/** Pulls a human-readable message out of a FastAPI error response. */
export function sectionErrorMessage(error: unknown, fallback: string): string {
	const detail = (error as SectionError | undefined)?.detail;

	if (typeof detail === "string") {
		return detail;
	}

	if (Array.isArray(detail) && detail.length > 0) {
		return detail.map((item) => item.msg).join(" ");
	}

	return fallback;
}

export function required(message: string) {
	return ({ value }: { value: string }) =>
		value.trim().length > 0 ? undefined : message;
}

const inputClassName =
	"w-full rounded-xl border border-border bg-field px-4 py-field text-ink outline-none transition-colors placeholder:text-ink-disabled focus:border-stroke aria-invalid:border-negative";

export function TextInput({
	error,
	label,
	...inputProps
}: {
	error?: string;
	label: string;
} & InputHTMLAttributes<HTMLInputElement>) {
	const id = useId();

	return (
		<div className="flex flex-col gap-1">
			<label className="text-ink-subtle text-sm" htmlFor={id}>
				{label}
			</label>
			<input
				aria-invalid={error !== undefined}
				className={inputClassName}
				id={id}
				{...inputProps}
			/>
			{error !== undefined && <p className="text-negative text-sm">{error}</p>}
		</div>
	);
}

export function FormError({ children }: { children: ReactNode }) {
	return (
		<p
			className="rounded-xl bg-negative-bg px-4 py-2 text-negative text-sm"
			role="alert"
		>
			{children}
		</p>
	);
}

/** Submit + delete row shared by every section form's footer. */
export function FormActions({
	deleting,
	isEditing,
	isSubmitting,
	canSubmit,
	onDelete,
	addLabel,
}: {
	deleting: boolean;
	isEditing: boolean;
	isSubmitting: boolean;
	canSubmit: boolean;
	onDelete: () => void;
	addLabel: string;
}) {
	return (
		<div className="flex items-center gap-3">
			{isEditing && (
				<Button
					disabled={deleting}
					onClick={onDelete}
					type="button"
					variant="danger"
				>
					{deleting ? "Deleting…" : "Delete"}
				</Button>
			)}

			<Button className="ml-auto" disabled={!canSubmit} type="submit">
				{isSubmitting ? "Saving…" : isEditing ? "Save changes" : addLabel}
			</Button>
		</div>
	);
}

/** Page chrome shared by every section's add/edit route: a back link, a title, and content below it. */
export function SectionFormPage({
	title,
	children,
}: {
	title: string;
	children: ReactNode;
}) {
	return (
		<main className="mx-auto w-full max-w-3xl px-4 py-16">
			<Link
				className="inline-flex items-center gap-1 text-sm text-ink-subtle transition-colors hover:text-ink"
				to="/sections"
			>
				<svg
					aria-hidden="true"
					fill="none"
					height="16"
					stroke="currentColor"
					strokeLinecap="round"
					strokeLinejoin="round"
					strokeWidth="2"
					viewBox="0 0 24 24"
					width="16"
				>
					<path d="M19 12H5M12 19l-7-7 7-7" />
				</svg>
				<span className="text-trim">Back to sections</span>
			</Link>

			<h1 className="mt-4 text-4xl leading-heading tracking-decreased">
				{title}
			</h1>

			<div className="mt-8">{children}</div>
		</main>
	);
}
