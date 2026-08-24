import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";

export type DropdownOption<TValue extends string = string> = {
	value: TValue;
	label: string;
	disabled?: boolean;
};

type DropdownProps<TValue extends string> = {
	className?: string;
	disabled?: boolean;
	emptyMessage?: string;
	id?: string;
	label?: string;
	onChange: (value: TValue) => void;
	options: DropdownOption<TValue>[];
	placeholder?: string;
	/** The selected option's value, or `""` when nothing is selected yet. */
	value: TValue | "";
};

/** Index of the next selectable option at or after `from`, wrapping around. */
function nextEnabledIndex<TValue extends string>(
	options: DropdownOption<TValue>[],
	from: number,
	step: 1 | -1,
): number {
	for (let offset = 0; offset < options.length; offset += 1) {
		const index =
			(((from + step * offset) % options.length) + options.length) %
			options.length;

		if (!options[index].disabled) {
			return index;
		}
	}

	return -1;
}

/**
 * A basic single-select dropdown built on a button + listbox, so it can be
 * styled with the app's tokens instead of the browser's native `<select>` chrome.
 *
 * Supports mouse and keyboard (arrows, Home/End, Enter/Space, Escape) and
 * closes when focus or a click leaves it.
 */
export function Dropdown<TValue extends string>({
	className,
	disabled = false,
	emptyMessage = "No options available.",
	id,
	label,
	onChange,
	options,
	placeholder = "Choose an option…",
	value,
}: DropdownProps<TValue>) {
	const generatedId = useId();
	const buttonId = id ?? generatedId;
	const listboxId = `${buttonId}-listbox`;
	const optionId = (index: number) => `${buttonId}-option-${index}`;

	const containerRef = useRef<HTMLDivElement>(null);
	const listRef = useRef<HTMLDivElement>(null);
	const [open, setOpen] = useState(false);
	const [activeIndex, setActiveIndex] = useState(-1);

	const selectedIndex = options.findIndex((option) => option.value === value);
	const selectedLabel =
		selectedIndex === -1 ? placeholder : options[selectedIndex].label;

	// Dismiss on a click anywhere outside the dropdown.
	useEffect(() => {
		if (!open) {
			return;
		}

		const onPointerDown = (event: PointerEvent) => {
			if (!containerRef.current?.contains(event.target as Node)) {
				setOpen(false);
			}
		};

		document.addEventListener("pointerdown", onPointerDown);
		return () => document.removeEventListener("pointerdown", onPointerDown);
	}, [open]);

	// Keep the highlighted option in view while arrowing through a long list.
	useEffect(() => {
		if (!open || activeIndex === -1) {
			return;
		}

		listRef.current?.children[activeIndex]?.scrollIntoView({
			block: "nearest",
		});
	}, [open, activeIndex]);

	const openMenu = (startAt: number) => {
		setOpen(true);
		setActiveIndex(
			options.length === 0 ? -1 : nextEnabledIndex(options, startAt, 1),
		);
	};

	const closeMenu = () => {
		setOpen(false);
		setActiveIndex(-1);
	};

	const select = (index: number) => {
		const option = options[index];

		if (option === undefined || option.disabled) {
			return;
		}

		onChange(option.value);
		closeMenu();
	};

	const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
		switch (event.key) {
			case "ArrowDown":
			case "ArrowUp": {
				event.preventDefault();
				const step = event.key === "ArrowDown" ? 1 : -1;

				if (!open) {
					openMenu(selectedIndex === -1 ? 0 : selectedIndex);
					return;
				}

				if (options.length > 0) {
					setActiveIndex(nextEnabledIndex(options, activeIndex + step, step));
				}
				return;
			}
			case "Home":
			case "End": {
				if (!open) {
					return;
				}
				event.preventDefault();
				setActiveIndex(
					event.key === "Home"
						? nextEnabledIndex(options, 0, 1)
						: nextEnabledIndex(options, options.length - 1, -1),
				);
				return;
			}
			case "Enter":
			case " ": {
				event.preventDefault();
				if (open) {
					select(activeIndex);
				} else {
					openMenu(selectedIndex === -1 ? 0 : selectedIndex);
				}
				return;
			}
			case "Escape": {
				if (open) {
					event.preventDefault();
					closeMenu();
				}
				return;
			}
			case "Tab": {
				closeMenu();
			}
		}
	};

	return (
		<div
			className={["flex flex-col gap-1", className].filter(Boolean).join(" ")}
		>
			{label && (
				<label className="text-ink-subtle text-sm" htmlFor={buttonId}>
					{label}
				</label>
			)}

			<div className="relative" ref={containerRef}>
				<button
					aria-activedescendant={
						open && activeIndex !== -1 ? optionId(activeIndex) : undefined
					}
					aria-controls={open ? listboxId : undefined}
					aria-expanded={open}
					aria-haspopup="listbox"
					className="flex w-full items-center justify-between gap-2 rounded-xl border border-border bg-field px-5 py-2 text-left text-ink outline-none transition-colors focus:border-stroke disabled:text-ink-disabled"
					disabled={disabled}
					id={buttonId}
					onClick={() =>
						open
							? closeMenu()
							: openMenu(selectedIndex === -1 ? 0 : selectedIndex)
					}
					onKeyDown={onKeyDown}
					role="combobox"
					type="button"
				>
					{/* No `text-trim` here: it shrinks the box to cap-height/baseline,
					    which `truncate`'s overflow clip would then cut descenders off. */}
					<span
						className={[
							"truncate",
							selectedIndex === -1 ? "text-ink-disabled" : "",
						]
							.filter(Boolean)
							.join(" ")}
					>
						{selectedLabel}
					</span>
					<svg
						aria-hidden="true"
						className={`shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
						fill="none"
						height="16"
						stroke="currentColor"
						strokeLinecap="round"
						strokeLinejoin="round"
						strokeWidth="2"
						viewBox="0 0 24 24"
						width="16"
					>
						<path d="m6 9 6 6 6-6" />
					</svg>
				</button>

				{open && (
					// The trigger keeps focus and points at the highlighted row with
					// aria-activedescendant, so the list itself is never focused.
					<div
						aria-labelledby={buttonId}
						className="absolute top-full right-0 left-0 z-10 mt-1 max-h-60 overflow-y-auto rounded-xl border border-border bg-surface py-1 shadow-card"
						id={listboxId}
						ref={listRef}
						role="listbox"
					>
						{options.length === 0 && (
							<p className="px-5 py-2 text-ink-subtle text-sm">
								{emptyMessage}
							</p>
						)}

						{options.map((option, index) => (
							// biome-ignore lint/a11y/useKeyWithClickEvents: keyboard users drive the list from the trigger button, never these rows.
							<div
								aria-disabled={option.disabled}
								aria-selected={index === selectedIndex}
								className={[
									"cursor-pointer px-5 py-2 text-ink",
									index === activeIndex ? "bg-btn-tertiary" : "",
									option.disabled ? "cursor-not-allowed text-ink-disabled" : "",
								]
									.filter(Boolean)
									.join(" ")}
								id={optionId(index)}
								key={option.value}
								onClick={() => select(index)}
								onMouseEnter={() => {
									if (!option.disabled) {
										setActiveIndex(index);
									}
								}}
								role="option"
								tabIndex={-1}
							>
								{option.label}
							</div>
						))}
					</div>
				)}
			</div>
		</div>
	);
}
