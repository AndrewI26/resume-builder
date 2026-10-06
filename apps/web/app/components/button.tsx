import type { ButtonHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary" | "tertiary" | "danger";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
	variant?: ButtonVariant;
};

const variantClasses: Record<ButtonVariant, string> = {
	primary:
		"bg-btn-primary text-btn-primary-fg disabled:bg-btn-primary-disabled disabled:text-btn-primary-disabled-fg",
	secondary:
		"border border-btn-secondary-border bg-btn-secondary text-btn-secondary-fg disabled:border-btn-secondary-disabled-border disabled:bg-btn-secondary-disabled disabled:text-btn-secondary-disabled-fg",
	tertiary:
		"bg-btn-tertiary text-btn-tertiary-fg disabled:bg-btn-tertiary-disabled disabled:text-btn-tertiary-disabled-fg",
	danger:
		"bg-btn-warning text-btn-warning-fg disabled:bg-disabled disabled:text-ink-disabled",
};

export function Button({
	children,
	className,
	type = "button",
	variant = "primary",
	...rest
}: ButtonProps) {
	return (
		<button
			className={[
				"inline-flex h-10 items-center justify-center rounded-button px-4 transition-opacity hover:opacity-90",
				variantClasses[variant],
				className,
			]
				.filter(Boolean)
				.join(" ")}
			type={type}
			{...rest}
		>
			<span className="text-trim">{children}</span>
		</button>
	);
}
