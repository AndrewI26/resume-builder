type TextFieldProps = {
	autoComplete: string;
	error?: string;
	label: string;
	name: string;
	onBlur: () => void;
	onChange: (value: string) => void;
	placeholder?: string;
	type: "email" | "password";
	value: string;
};

export function TextField({
	autoComplete,
	error,
	label,
	name,
	onBlur,
	onChange,
	placeholder,
	type,
	value,
}: TextFieldProps) {
	return (
		<div className="flex flex-col gap-1">
			<label className="text-sm text-ink-subtle" htmlFor={name}>
				{label}
			</label>
			<input
				aria-invalid={error !== undefined}
				autoComplete={autoComplete}
				className="w-full rounded-xl border border-border bg-field px-4 py-2 text-ink outline-none transition-colors placeholder:text-ink-disabled focus:border-stroke aria-[invalid=true]:border-negative"
				id={name}
				name={name}
				onBlur={onBlur}
				onChange={(event) => onChange(event.target.value)}
				placeholder={placeholder}
				type={type}
				value={value}
			/>
			{error !== undefined && <p className="text-sm text-negative">{error}</p>}
		</div>
	);
}
