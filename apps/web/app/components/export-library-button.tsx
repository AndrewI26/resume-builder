import { Button } from "@components/button";
import { FormError } from "@components/section-form";
import { useState } from "react";
import { downloadLibraryExport } from "~/lib/library/export";

/** Downloads the whole library as JSON, in the format import reads. */
export function ExportLibraryButton() {
	const [exporting, setExporting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const exportLibrary = async () => {
		setExporting(true);
		setError(null);
		try {
			await downloadLibraryExport();
		} catch (caught) {
			setError(
				caught instanceof Error
					? caught.message
					: "Could not export your library.",
			);
		} finally {
			setExporting(false);
		}
	};

	return (
		<div className="flex flex-col items-start gap-2">
			<Button disabled={exporting} onClick={exportLibrary} variant="secondary">
				{exporting ? "Exporting…" : "Export library"}
			</Button>
			{error !== null && <FormError>{error}</FormError>}
		</div>
	);
}
