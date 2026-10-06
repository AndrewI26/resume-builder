import { $api } from "@api/api";
import type { components } from "@api/schema.d.ts";
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
	return [{ title: "Education · Resume Builder" }];
}

function EducationForm({
	initialValue,
	onSaved,
}: {
	initialValue?: components["schemas"]["EducationRead"];
	onSaved: () => void;
}) {
	const isEditing = initialValue !== undefined;
	const queryClient = useQueryClient();
	const [formError, setFormError] = useState<string | null>(null);
	const [deleting, setDeleting] = useState(false);
	const { mutateAsync: createEducation } = $api.useMutation(
		"post",
		"/education/",
	);
	const { mutateAsync: editEducation } = $api.useMutation(
		"put",
		"/education/{education_id}",
	);
	const { mutateAsync: deleteEducation } = $api.useMutation(
		"delete",
		"/education/{education_id}",
	);

	const invalidate = () =>
		queryClient.invalidateQueries({
			queryKey: $api.queryOptions("get", "/education/").queryKey,
		});

	const form = useForm({
		defaultValues: {
			name: initialValue?.name ?? "",
			subheading: initialValue?.subheading ?? "",
			duration: initialValue?.duration ?? "",
			location: initialValue?.location ?? "",
		},
		onSubmit: async ({ value }) => {
			setFormError(null);
			try {
				if (initialValue) {
					await editEducation({
						body: value,
						params: { path: { education_id: initialValue.id } },
					});
				} else {
					await createEducation({ body: value });
				}
				await invalidate();
				onSaved();
			} catch (error) {
				setFormError(
					sectionErrorMessage(error, "Could not save education. Try again."),
				);
			}
		},
	});

	const handleDelete = async () => {
		if (
			initialValue === undefined ||
			!window.confirm("Delete this education entry? This can't be undone.")
		) {
			return;
		}

		setDeleting(true);
		setFormError(null);
		try {
			await deleteEducation({
				params: { path: { education_id: initialValue.id } },
			});
			await invalidate();
			onSaved();
		} catch (error) {
			setFormError(
				sectionErrorMessage(error, "Could not delete education. Try again."),
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
				name="name"
				validators={{ onSubmit: required("Enter a school.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Name"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="University of Waterloo"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field
				name="subheading"
				validators={{ onSubmit: required("Enter a subheading.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Subheading"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="Computer Science (B.A.Sc.) - 3.7/4.00 GPA (70% CAV)"
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
						placeholder="2018 – 2022"
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

			{formError && <FormError>{formError}</FormError>}

			<form.Subscribe
				selector={(state) => [state.canSubmit, state.isSubmitting] as const}
			>
				{([canSubmit, isSubmitting]) => (
					<FormActions
						addLabel="Add education"
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

export default function EducationSectionRoute() {
	const { educationId } = useParams();
	const isNew = educationId === undefined;
	const navigate = useNavigate();
	const goBack = () => navigate("/sections");

	const query = $api.useQuery(
		"get",
		"/education/{education_id}",
		{ params: { path: { education_id: educationId ?? "" } } },
		{ enabled: !isNew },
	);

	return (
		<SectionFormPage title={isNew ? "Add education" : "Edit education"}>
			{isNew ? (
				<EducationForm onSaved={goBack} />
			) : query.isPending ? (
				<p className="text-ink-subtle text-sm">Loading…</p>
			) : query.isError || !query.data ? (
				<p className="text-negative text-sm">Could not load this entry.</p>
			) : (
				<EducationForm initialValue={query.data} onSaved={goBack} />
			)}
		</SectionFormPage>
	);
}
