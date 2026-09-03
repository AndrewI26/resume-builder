import { $api } from "@api/api";
import type { components } from "@api/schema.d.ts";
import {
	type BulletPointDraft,
	BulletPointsField,
	emptyBulletPoint,
	fromApiBulletPoints,
	toApiBulletPoints,
} from "@components/bullet-points-field";
import {
	FormActions,
	FormError,
	required,
	sectionErrorMessage,
	SectionFormPage,
	TextInput,
} from "@components/section-form";
import { useForm } from "@tanstack/react-form";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router";

export function meta() {
	return [{ title: "Experience · Resume Builder" }];
}

function ExperienceForm({
	initialValue,
	onSaved,
}: {
	initialValue?: components["schemas"]["ExpirenceRead"];
	onSaved: () => void;
}) {
	const isEditing = initialValue !== undefined;
	const queryClient = useQueryClient();
	const [formError, setFormError] = useState<string | null>(null);
	const [deleting, setDeleting] = useState(false);
	const { mutateAsync: createExperience } = $api.useMutation(
		"post",
		"/experience/",
	);
	const { mutateAsync: editExperience } = $api.useMutation(
		"put",
		"/experience/{expirence_id}",
	);
	const { mutateAsync: deleteExperience } = $api.useMutation(
		"delete",
		"/experience/{expirence_id}",
	);

	const invalidate = () =>
		queryClient.invalidateQueries({
			queryKey: $api.queryOptions("get", "/experience/").queryKey,
		});

	const form = useForm({
		defaultValues: {
			company: initialValue?.company ?? "",
			position: initialValue?.position ?? "",
			duration: initialValue?.duration ?? "",
			location: initialValue?.location ?? "",
			bulletPoints: initialValue
				? fromApiBulletPoints(initialValue.bullet_points)
				: ([emptyBulletPoint()] as BulletPointDraft[]),
		},
		onSubmit: async ({ value }) => {
			setFormError(null);
			try {
				const body = {
					company: value.company,
					position: value.position,
					duration: value.duration,
					location: value.location,
					bullet_points: toApiBulletPoints(value.bulletPoints),
				};

				if (initialValue) {
					await editExperience({
						body,
						params: { path: { expirence_id: initialValue.id } },
					});
				} else {
					await createExperience({ body });
				}
				await invalidate();
				onSaved();
			} catch (error) {
				setFormError(
					sectionErrorMessage(error, "Could not save experience. Try again."),
				);
			}
		},
	});

	const handleDelete = async () => {
		if (
			initialValue === undefined ||
			!window.confirm("Delete this experience entry? This can't be undone.")
		) {
			return;
		}

		setDeleting(true);
		setFormError(null);
		try {
			await deleteExperience({
				params: { path: { expirence_id: initialValue.id } },
			});
			await invalidate();
			onSaved();
		} catch (error) {
			setFormError(
				sectionErrorMessage(error, "Could not delete experience. Try again."),
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
			<form.Field
				name="position"
				validators={{ onSubmit: required("Enter a position.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Position"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="Software Engineer"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field
				name="company"
				validators={{ onSubmit: required("Enter a company.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Company"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="Acme Corp"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field
				name="duration"
				validators={{ onSubmit: required("Enter a duration.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Duration"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="2022 – Present"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field
				name="location"
				validators={{ onSubmit: required("Enter a location.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Location"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="Remote"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field name="bulletPoints">
				{(field) => (
					<BulletPointsField
						label="Bullet points"
						onChange={field.handleChange}
						value={field.state.value}
					/>
				)}
			</form.Field>

			{formError && <FormError>{formError}</FormError>}

			<form.Subscribe
				selector={(state) => [state.canSubmit, state.isSubmitting] as const}
			>
				{([canSubmit, isSubmitting]) => (
					<FormActions
						addLabel="Add experience"
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

export default function ExperienceSectionRoute() {
	const { experienceId } = useParams();
	const isNew = experienceId === undefined;
	const navigate = useNavigate();
	const goBack = () => navigate("/sections");

	const query = $api.useQuery(
		"get",
		"/experience/{expirence_id}",
		{ params: { path: { expirence_id: experienceId ?? "" } } },
		{ enabled: !isNew },
	);

	return (
		<SectionFormPage title={isNew ? "Add experience" : "Edit experience"}>
			{isNew ? (
				<ExperienceForm onSaved={goBack} />
			) : query.isPending ? (
				<p className="text-ink-subtle text-sm">Loading…</p>
			) : query.isError || !query.data ? (
				<p className="text-negative text-sm">Could not load this entry.</p>
			) : (
				<ExperienceForm
					initialValue={query.data as components["schemas"]["ExpirenceRead"]}
					onSaved={goBack}
				/>
			)}
		</SectionFormPage>
	);
}
