import type { ReactNode } from "react";

export type Column<T> = {
	key: string;
	header: string;
	render: (row: T) => ReactNode;
};

type TableProps<T> = {
	className?: string;
	columns: Column<T>[];
	data: T[];
	emptyMessage?: string;
	getRowKey: (row: T) => string;
	onRowClick?: (row: T) => void;
};

export function Table<T>({
	className,
	columns,
	data,
	emptyMessage = "Nothing here yet.",
	getRowKey,
	onRowClick,
}: TableProps<T>) {
	if (data.length === 0) {
		return (
			<p className={["text-ink-subtle", className].filter(Boolean).join(" ")}>
				{emptyMessage}
			</p>
		);
	}

	return (
		<div
			className={[
				"overflow-hidden rounded-card border border-border",
				className,
			]
				.filter(Boolean)
				.join(" ")}
		>
			<table className="w-full text-left">
				<thead>
					<tr className="border-border border-b">
						{columns.map((column) => (
							<th
								className="px-4 py-3 text-sm font-medium text-ink-subtle"
								key={column.key}
							>
								{column.header}
							</th>
						))}
					</tr>
				</thead>
				<tbody>
					{data.map((row) => (
						<tr
							className={[
								"border-border border-b last:border-0",
								onRowClick && "cursor-pointer transition-colors hover:bg-field",
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
							role={onRowClick && "button"}
							tabIndex={onRowClick && 0}
						>
							{columns.map((column) => (
								<td className="px-4 py-3 text-ink" key={column.key}>
									{column.render(row)}
								</td>
							))}
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}
