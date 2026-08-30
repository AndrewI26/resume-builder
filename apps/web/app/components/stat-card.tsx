import type { ReactNode } from "react";
import { Link } from "react-router";

/** The tint used for the icon tile.
 *
 * Each entry pairs a solid foreground with the same hue at low alpha for the
 * tile behind it. Written out in full because Tailwind scans for whole class
 * names — building these by interpolation would leave the classes uncompiled.
 */
const accentClasses = {
	blue: "bg-accent-blue/12 text-accent-blue",
	green: "bg-accent-green/12 text-accent-green",
	purple: "bg-chip-purple/12 text-chip-purple",
	pink: "bg-chip-pink/12 text-chip-pink",
	orange: "bg-chip-orange/12 text-chip-orange",
} as const;

export type StatCardAccent = keyof typeof accentClasses;

type StatCardProps = {
	accent?: StatCardAccent;
	className?: string;
	/** Sits under the label: what the number counts, or how to read it. */
	description?: string;
	icon: ReactNode;
	label: string;
	/** When set the whole card becomes a link to this route. */
	to?: string;
	value: ReactNode;
};

export function StatCard({
	accent = "blue",
	className,
	description,
	icon,
	label,
	to,
	value,
}: StatCardProps) {
	const content = (
		<>
			<div className="flex items-center justify-between gap-4">
				<span
					aria-hidden="true"
					className={[
						"inline-flex size-10 shrink-0 items-center justify-center rounded-xl",
						accentClasses[accent],
					].join(" ")}
				>
					{icon}
				</span>

				<span className="text-5xl leading-heading tracking-decreased">
					<span className="text-trim">{value}</span>
				</span>
			</div>

			<div className="mt-6 flex items-end justify-between gap-4">
				<span>
					<span className="block text-ink text-lg">
						<span className="text-trim">{label}</span>
					</span>
					{description !== undefined && (
						<span className="mt-1 block text-ink-subtle leading-body">
							{description}
						</span>
					)}
				</span>

				{to !== undefined && (
					<span
						aria-hidden="true"
						className="shrink-0 pb-1 text-icon-inactive transition-[transform,color] duration-200 ease-out group-hover:translate-x-1 group-hover:text-ink"
					>
						<svg
							fill="none"
							height="16"
							stroke="currentColor"
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth="2"
							viewBox="0 0 24 24"
							width="16"
						>
							<title>Open</title>
							<path d="M9 6l6 6-6 6" />
						</svg>
					</span>
				)}
			</div>
		</>
	);

	const baseClassName = [
		"rounded-card border border-border bg-card-secondary p-6",
		className,
	]
		.filter(Boolean)
		.join(" ");

	if (to === undefined) {
		return <div className={baseClassName}>{content}</div>;
	}

	return (
		<Link
			className={`group block text-left transition-colors duration-200 ease-out hover:bg-card-hover ${baseClassName}`}
			to={to}
		>
			{content}
		</Link>
	);
}
