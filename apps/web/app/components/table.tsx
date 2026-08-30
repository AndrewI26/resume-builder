import type { ReactNode } from "react";

export type Column<T> = {
	key: string;
	header: string;
	render: (row: T) => ReactNode;
	/**
	 * Which edge the column hangs off. Numbers and other trailing values read
	 * better flushed right, the way a statement lines its figures up.
	 */
	align?: "left" | "right";
};

type TableProps<T> = {
	className?: string;
	columns: Column<T>[];
	data: T[];
	emptyMessage?: string;
	getRowKey: (row: T) => string;
	onRowClick?: (row: T) => void;
};

const alignClass = (align: Column<unknown>["align"]) =>
	align === "right" ? "text-right" : "text-left";

/**
 * A card that happens to contain a table: one surface, a single rule under the
 * header, and no lines between rows — the rows are separated by their own
 * breathing room instead. Wide tables scroll inside the card rather than
 * pushing the page sideways.
 */
export function Table<T>({
	className,
	columns,
	data,
	emptyMessage = "Nothing here yet.",
	getRowKey,
	onRowClick,
}: TableProps<T>) {
	return (
		<div
			className={[
				"overflow-hidden rounded-table bg-table shadow-raised dark:border dark:border-table-border dark:shadow-none",
				className,
			]
				.filter(Boolean)
				.join(" ")}
		>
			{data.length === 0 ? (
				<p className="px-6 py-8 text-center text-ink-subtle text-sm">
					{emptyMessage}
				</p>
			) : (
				<div className="overflow-x-auto">
					<table className="w-full border-collapse">
						<thead>
							<tr className="border-table-border border-b">
								{columns.map((column) => (
									<th
										className={[
											"whitespace-nowrap px-6 py-4 font-normal text-sm text-table-header-ink",
											alignClass(column.align),
										].join(" ")}
										key={column.key}
										scope="col"
									>
										<span className="text-trim">{column.header}</span>
									</th>
								))}
							</tr>
						</thead>
						<tbody>
							{data.map((row) => (
								<tr
									className={[
										"transition-colors hover:bg-table-row-hover",
										onRowClick && "cursor-pointer",
									]
										.filter(Boolean)
										.join(" ")}
									key={getRowKey(row)}
									onClick={onRowClick && (() => onRowClick(row))}
									onKeyDown={
										onRowClick &&
										((event) => {
											if (event.key === "Enter" || event.key === " ") {
												event.preventDefault();
												onRowClick(row);
											}
										})
									}
									role={onRowClick ? "button" : undefined}
									tabIndex={onRowClick ? 0 : undefined}
								>
									{columns.map((column) => (
										<td
											className={[
												"px-6 py-4 text-ink text-sm",
												alignClass(column.align),
											].join(" ")}
											key={column.key}
										>
											{column.render(row)}
										</td>
									))}
								</tr>
							))}
						</tbody>
					</table>
				</div>
			)}
		</div>
	);
}
