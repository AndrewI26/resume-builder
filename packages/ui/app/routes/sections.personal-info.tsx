import { $api } from "@api/api";
import type { components } from "@api/schema.d.ts";
import {
	FormActions,
	FormError,
	sectionErrorMessage,
	SectionFormPage,
	TextInput,
} from "@components/section-form";
import { useForm } from "@tanstack/react-form";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router";

export function meta() {
	return [{ title: "Personal info · Resume Builder" }];
}

/** A URL plus the text a resume shows in its place, once a URL is given. */
function buildLink(
	url: string,
	label: string,
): { url: string; label?: string } | undefined {
	const trimmedUrl = url.trim();
	if (!trimmedUrl) return undefined;

	return { url: trimmedUrl, label: label.trim() || undefined };
}

function PersonalInfoForm({
	initialValue,
	onSaved,
}: {
	initialValue?: components["schemas"]["PersonalInfoRead"];
	onSaved: () => void;
}) {
	const isEditing = initialValue !== undefined;
	const queryClient = useQueryClient();
	const [formError, setFormError] = useState<string | null>(null);
	const [deleting, setDeleting] = useState(false);
	const { mutateAsync: createPersonalInfo } = $api.useMutation(
		"post",
		"/personal-info/",
	);
	const { mutateAsync: editPersonalInfo } = $api.useMutation(
		"put",
		"/personal-info/{personal_info_id}",
	);
	const { mutateAsync: deletePersonalInfo } = $api.useMutation(
		"delete",
		"/personal-info/{personal_info_id}",
	);

	const invalidate = () =>
		queryClient.invalidateQueries({
			queryKey: $api.queryOptions("get", "/personal-info/").queryKey,
		});

	const form = useForm({
		defaultValues: {
			email: initialValue?.email ?? "",
			phone_number: initialValue?.phone_number ?? "",
			address: initialValue?.address ?? "",
			github_url: initialValue?.github?.url ?? "",
			github_label: initialValue?.github?.label ?? "",
			linkedin_url: initialValue?.linkedin?.url ?? "",
			linkedin_label: initialValue?.linkedin?.label ?? "",
			portfolio_url: initialValue?.portfolio?.url ?? "",
			portfolio_label: initialValue?.portfolio?.label ?? "",
		},
		onSubmit: async ({ value }) => {
			setFormError(null);
			try {
				const body = {
					email: value.email.trim() || undefined,
					phone_number: value.phone_number.trim() || undefined,
					address: value.address.trim() || undefined,
					github: buildLink(value.github_url, value.github_label),
					linkedin: buildLink(value.linkedin_url, value.linkedin_label),
					portfolio: buildLink(value.portfolio_url, value.portfolio_label),
				};

				if (initialValue) {
					await editPersonalInfo({
						body,
						params: { path: { personal_info_id: initialValue.id } },
					});
				} else {
					await createPersonalInfo({ body });
				}
				await invalidate();
				onSaved();
			} catch (error) {
				setFormError(
					sectionErrorMessage(
						error,
						"Could not save personal info. Try again.",
					),
				);
			}
		},
	});

	const handleDelete = async () => {
		if (
			initialValue === undefined ||
			!window.confirm("Delete this personal info entry? This can't be undone.")
		) {
			return;
		}

		setDeleting(true);
		setFormError(null);
		try {
			await deletePersonalInfo({
				params: { path: { personal_info_id: initialValue.id } },
			});
			await invalidate();
			onSaved();
		} catch (error) {
			setFormError(
				sectionErrorMessage(
					error,
					"Could not delete personal info. Try again.",
				),
			);
			setDeleting(false);
		}
	};

	return (
		<form
			className="flex flex-col gap-4"
			noValidate
			onSubmit={(event) => {
				event.preventDefault();
				form.handleSubmit();
			}}
		>
			<form.Field name="email">
				{(field) => (
					<TextInput
						label="Email"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="you@example.com"
						type="email"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field name="phone_number">
				{(field) => (
					<TextInput
						label="Phone"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="555-555-5555"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field name="address">
				{(field) => (
					<TextInput
						label="Address"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="City, State"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<div className="flex flex-col gap-3 rounded-xl border border-border p-3">
				<p className="text-ink-subtle text-sm">GitHub</p>

				<form.Field name="github_url">
					{(field) => (
						<TextInput
							label="URL"
							onChange={(event) => field.handleChange(event.target.value)}
							placeholder="https://github.com/you"
							value={field.state.value}
						/>
					)}
				</form.Field>

				<form.Field name="github_label">
					{(field) => (
						<TextInput
							label="Display name (optional)"
							onChange={(event) => field.handleChange(event.target.value)}
							placeholder="github.com/you"
							value={field.state.value}
						/>
					)}
				</form.Field>
			</div>

			<div className="flex flex-col gap-3 rounded-xl border border-border p-3">
				<p className="text-ink-subtle text-sm">LinkedIn</p>

				<form.Field name="linkedin_url">
					{(field) => (
						<TextInput
							label="URL"
							onChange={(event) => field.handleChange(event.target.value)}
							placeholder="https://linkedin.com/in/you"
							value={field.state.value}
						/>
					)}
				</form.Field>

				<form.Field name="linkedin_label">
					{(field) => (
						<TextInput
							label="Display name (optional)"
							onChange={(event) => field.handleChange(event.target.value)}
							placeholder="linkedin.com/in/you"
							value={field.state.value}
						/>
					)}
				</form.Field>
			</div>

			<div className="flex flex-col gap-3 rounded-xl border border-border p-3">
				<p className="text-ink-subtle text-sm">Portfolio</p>

				<form.Field name="portfolio_url">
					{(field) => (
						<TextInput
							label="URL"
							onChange={(event) => field.handleChange(event.target.value)}
							placeholder="https://you.dev"
							value={field.state.value}
						/>
					)}
				</form.Field>

				<form.Field name="portfolio_label">
					{(field) => (
						<TextInput
							label="Display name (optional)"
							onChange={(event) => field.handleChange(event.target.value)}
							placeholder="Portfolio"
							value={field.state.value}
						/>
					)}
				</form.Field>
			</div>

			{formError && <FormError>{formError}</FormError>}

			<form.Subscribe
				selector={(state) => [state.canSubmit, state.isSubmitting] as const}
			>
				{([canSubmit, isSubmitting]) => (
					<FormActions
						addLabel="Add personal info"
						canSubmit={canSubmit}
						deleting={deleting}
						isEditing={isEditing}
						isSubmitting={isSubmitting}
						onDelete={handleDelete}
					/>
				)}
			</form.Subscribe>
		</form>
	);
}

export default function PersonalInfoSectionRoute() {
	const { personalInfoId } = useParams();
	const isNew = personalInfoId === undefined;
	const navigate = useNavigate();
	const goBack = () => navigate("/sections");

	const query = $api.useQuery(
		"get",
		"/personal-info/{personal_info_id}",
		{ params: { path: { personal_info_id: personalInfoId ?? "" } } },
		{ enabled: !isNew },
	);

	return (
		<SectionFormPage title={isNew ? "Add personal info" : "Edit personal info"}>
			{isNew ? (
				<PersonalInfoForm onSaved={goBack} />
			) : query.isPending ? (
				<p className="text-ink-subtle text-sm">Loading…</p>
			) : query.isError || !query.data ? (
				<p className="text-negative text-sm">Could not load this entry.</p>
			) : (
				<PersonalInfoForm initialValue={query.data} onSaved={goBack} />
			)}
		</SectionFormPage>
	);
}
