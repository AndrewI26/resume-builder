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
import {
	emptySkillItem,
	fromApiSkillItems,
	type SkillItemDraft,
	SkillItemsField,
	toApiSkillItems,
} from "@components/skill-items-field";
import { useForm } from "@tanstack/react-form";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router";

export function meta() {
	return [{ title: "Skills · Resume Builder" }];
}

function SkillForm({
	initialValue,
	onSaved,
}: {
	initialValue?: components["schemas"]["SkillRead"];
	onSaved: () => void;
}) {
	const isEditing = initialValue !== undefined;
	const queryClient = useQueryClient();
	const [formError, setFormError] = useState<string | null>(null);
	const [deleting, setDeleting] = useState(false);
	const { mutateAsync: createSkill } = $api.useMutation("post", "/skill/");
	const { mutateAsync: editSkill } = $api.useMutation(
		"put",
		"/skill/{skill_id}",
	);
	const { mutateAsync: deleteSkill } = $api.useMutation(
		"delete",
		"/skill/{skill_id}",
	);

	const invalidate = () =>
		queryClient.invalidateQueries({
			queryKey: $api.queryOptions("get", "/skill/").queryKey,
		});

	const form = useForm({
		defaultValues: {
			name: initialValue?.name ?? "",
			items: initialValue
				? fromApiSkillItems(initialValue.items)
				: ([emptySkillItem()] as SkillItemDraft[]),
		},
		onSubmit: async ({ value }) => {
			setFormError(null);
			try {
				const items = toApiSkillItems(value.items);

				if (initialValue) {
					await editSkill({
						body: { items, name: value.name, position: initialValue.position },
						params: { path: { skill_id: initialValue.id } },
					});
				} else {
					await createSkill({ body: { items, name: value.name } });
				}
				await invalidate();
				onSaved();
			} catch (error) {
				setFormError(
					sectionErrorMessage(error, "Could not save skill. Try again."),
				);
			}
		},
	});

	const handleDelete = async () => {
		if (
			initialValue === undefined ||
			!window.confirm("Delete this skill? This can't be undone.")
		) {
			return;
		}

		setDeleting(true);
		setFormError(null);
		try {
			await deleteSkill({ params: { path: { skill_id: initialValue.id } } });
			await invalidate();
			onSaved();
		} catch (error) {
			setFormError(
				sectionErrorMessage(error, "Could not delete skill. Try again."),
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
						placeholder="Languages"
						value={field.state.value}
					/>
				)}
			</form.Field>

			<form.Field
				name="items"
				validators={{
					onSubmit: ({ value }) =>
						toApiSkillItems(value).length > 0
							? undefined
							: "Enter at least one skill.",
				}}
			>
				{(field) => (
					<SkillItemsField
						error={field.state.meta.errors[0]}
						label="Skills"
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
						addLabel="Add skill"
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

export default function SkillSectionRoute() {
	const { skillId } = useParams();
	const isNew = skillId === undefined;
	const navigate = useNavigate();
	const goBack = () => navigate("/sections");

	const query = $api.useQuery(
		"get",
		"/skill/{skill_id}",
		{ params: { path: { skill_id: skillId ?? "" } } },
		{ enabled: !isNew },
	);

	return (
		<SectionFormPage title={isNew ? "Add skill" : "Edit skill"}>
			{isNew ? (
				<SkillForm onSaved={goBack} />
			) : query.isPending ? (
				<p className="text-ink-subtle text-sm">Loading…</p>
			) : query.isError || !query.data ? (
				<p className="text-negative text-sm">Could not load this entry.</p>
			) : (
				<SkillForm initialValue={query.data} onSaved={goBack} />
			)}
		</SectionFormPage>
	);
}
