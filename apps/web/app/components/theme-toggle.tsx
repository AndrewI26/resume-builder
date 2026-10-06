import { useTheme } from "~/theme/use-theme";

export function ThemeToggle() {
	const { theme, toggleTheme } = useTheme();
	const isDark = theme === "dark";

	return (
		<button
			aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
			className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-btn-tertiary text-btn-tertiary-fg transition-opacity hover:opacity-90"
			onClick={toggleTheme}
			type="button"
		>
			{isDark ? (
				<svg
					aria-hidden="true"
					fill="none"
					height="18"
					stroke="currentColor"
					strokeLinecap="round"
					strokeLinejoin="round"
					strokeWidth="2"
					viewBox="0 0 24 24"
					width="18"
				>
					<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z" />
				</svg>
			) : (
				<svg
					aria-hidden="true"
					fill="none"
					height="18"
					stroke="currentColor"
					strokeLinecap="round"
					strokeLinejoin="round"
					strokeWidth="2"
					viewBox="0 0 24 24"
					width="18"
				>
					<circle cx="12" cy="12" r="4" />
					<path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
				</svg>
			)}
		</button>
	);
}
