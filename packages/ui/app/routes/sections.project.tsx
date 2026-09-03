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
	return [{ title: "Projects · Resume Builder" }];
}

function splitList(text: string): string[] {
	return text
		.split(",")
		.map((item) => item.trim())
		.filter((item) => item.length > 0);
}

function ProjectForm({
	initialValue,
	onSaved,
}: {
	initialValue?: components["schemas"]["ProjectRead"];
	onSaved: () => void;
}) {
	const isEditing = initialValue !== undefined;
	const queryClient = useQueryClient();
	const [formError, setFormError] = useState<string | null>(null);
	const [deleting, setDeleting] = useState(false);
	const { mutateAsync: createProject } = $api.useMutation("post", "/project/");
	const { mutateAsync: editProject } = $api.useMutation(
		"put",
		"/project/{project_id}",
	);
	const { mutateAsync: deleteProject } = $api.useMutation(
		"delete",
		"/project/{project_id}",
	);

	const invalidate = () =>
		queryClient.invalidateQueries({
			queryKey: $api.queryOptions("get", "/project/").queryKey,
		});

	const form = useForm({
		defaultValues: {
			name: initialValue?.name ?? "",
			link: initialValue?.link ?? "",
			technologiesText: initialValue
				? initialValue.technologies.join(", ")
				: "",
			bulletPoints: initialValue
				? fromApiBulletPoints(initialValue.bullet_points)
				: ([emptyBulletPoint()] as BulletPointDraft[]),
		},
		onSubmit: async ({ value }) => {
			setFormError(null);
			try {
				const body = {
					name: value.name,
					link: value.link.trim() || undefined,
					technologies: splitList(value.technologiesText),
					bullet_points: toApiBulletPoints(value.bulletPoints),
				};

				if (initialValue) {
					await editProject({
						body,
						params: { path: { project_id: initialValue.id } },
					});
				} else {
					await createProject({ body });
				}
				await invalidate();
				onSaved();
			} catch (error) {
				setFormError(
					sectionErrorMessage(error, "Could not save project. Try again."),
				);
			}
		},
	});

	const handleDelete = async () => {
		if (
			initialValue === undefined ||
			!window.confirm("Delete this project? This can't be undone.")
		) {
			return;
		}

		setDeleting(true);
		setFormError(null);
		try {
			await deleteProject({
				params: { path: { project_id: initialValue.id } },
			});
			await invalidate();
			onSaved();
		} catch (error) {
			setFormError(
				sectionErrorMessage(error, "Could not delete project. Try again."),
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
				validators={{ onSubmit: required("Enter a name.") }}
			>
				{(field) => (
					<TextInput
						error={field.state.meta.errors[0]}
						label="Name"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="Resume Builder"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field name="link">
				{(field) => (
					<TextInput
						label="Link"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="https://github.com/you/project"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field name="technologiesText">
				{(field) => (
					<TextInput
						label="Technologies (comma separated)"
						onChange={(event) => field.handleChange(event.target.value)}
						placeholder="React, FastAPI, Postgres"
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
						addLabel="Add project"
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

export default function ProjectSectionRoute() {
	const { projectId } = useParams();
	const isNew = projectId === undefined;
	const navigate = useNavigate();
	const goBack = () => navigate("/sections");

	const query = $api.useQuery(
		"get",
		"/project/{project_id}",
		{ params: { path: { project_id: projectId ?? "" } } },
		{ enabled: !isNew },
	);

	return (
		<SectionFormPage title={isNew ? "Add project" : "Edit project"}>
			{isNew ? (
				<ProjectForm onSaved={goBack} />
			) : query.isPending ? (
				<p className="text-ink-subtle text-sm">Loading…</p>
			) : query.isError || !query.data ? (
				<p className="text-negative text-sm">Could not load this entry.</p>
			) : (
				<ProjectForm
					initialValue={query.data as components["schemas"]["ProjectRead"]}
					onSaved={goBack}
				/>
			)}
		</SectionFormPage>
	);
}
