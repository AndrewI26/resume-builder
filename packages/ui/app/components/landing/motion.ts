/**
 * The small amount of motion machinery the landing page's demos share.
 *
 * Nothing here is a dependency: a FLIP helper on the Web Animations API, an
 * in-view check, and an autoplay timer that gives way to the visitor. All of
 * it stands down under `prefers-reduced-motion`.
 */

import {
	type RefObject,
	useCallback,
	useEffect,
	useLayoutEffect,
	useRef,
	useState,
} from "react";

/** The app's "settle" curve: quick out of the gate, long soft landing. */
export const EASE = "cubic-bezier(0.2, 0, 0, 1)";

function reducedMotion(): boolean {
	return (
		typeof window !== "undefined" &&
		window.matchMedia("(prefers-reduced-motion: reduce)").matches
	);
}

export function usePrefersReducedMotion(): boolean {
	const [reduced, setReduced] = useState(false);

	useEffect(() => {
		const query = window.matchMedia("(prefers-reduced-motion: reduce)");
		setReduced(query.matches);
		const onChange = () => setReduced(query.matches);
		query.addEventListener("change", onChange);
		return () => query.removeEventListener("change", onChange);
	}, []);

	return reduced;
}

export interface Flip {
	/** Record where everything is now. Call it just before the state change. */
	capture: () => void;
	/**
	 * A ref for one moving element. With a `parent`, the element is measured
	 * relative to that one, so a row inside a heading that moves does not get
	 * the heading's journey a second time on top of its own.
	 */
	register: (
		key: string,
		parent?: string,
	) => (node: HTMLElement | null) => void;
}

type Point = { x: number; y: number };

/**
 * Animates keyed elements from where they were to where a re-render put them.
 *
 * `capture` takes the snapshot rather than a pre-commit hook, because React
 * has no such hook for function components — and taking it from the live,
 * possibly mid-flight position is what lets a second move interrupt the first
 * without a jump.
 */
export function useFlip(duration = 520): Flip {
	const nodes = useRef(
		new Map<string, { node: HTMLElement; parent?: string }>(),
	);
	const callbacks = useRef(
		new Map<string, (node: HTMLElement | null) => void>(),
	);
	const snapshot = useRef<Map<string, Point> | null>(null);
	const running = useRef<Animation[]>([]);

	const position = useCallback((key: string): Point | null => {
		const item = nodes.current.get(key);
		if (!item) {
			return null;
		}

		const box = item.node.getBoundingClientRect();
		const parent = item.parent ? nodes.current.get(item.parent) : undefined;
		if (!parent) {
			return { x: box.left, y: box.top };
		}

		const outer = parent.node.getBoundingClientRect();
		return { x: box.left - outer.left, y: box.top - outer.top };
	}, []);

	const capture = useCallback(() => {
		const points = new Map<string, Point>();
		for (const key of nodes.current.keys()) {
			const point = position(key);
			if (point) {
				points.set(key, point);
			}
		}
		snapshot.current = points;
	}, [position]);

	const register = useCallback((key: string, parent?: string) => {
		const id = `${parent ?? ""}/${key}`;
		let callback = callbacks.current.get(id);
		if (!callback) {
			callback = (node) => {
				if (node) {
					nodes.current.set(key, { node, parent });
				} else {
					nodes.current.delete(key);
				}
			};
			callbacks.current.set(id, callback);
		}
		return callback;
	}, []);

	// every render, on purpose: it only acts when a snapshot is waiting
	useLayoutEffect(() => {
		const before = snapshot.current;
		if (!before) {
			return;
		}
		snapshot.current = null;

		if (reducedMotion()) {
			return;
		}

		// measure the resting layout, not wherever the last move had got to
		for (const animation of running.current) {
			animation.cancel();
		}
		running.current = [];

		const moves: { node: HTMLElement; dx: number; dy: number }[] = [];
		for (const [key, { node }] of nodes.current) {
			const from = before.get(key);
			const to = position(key);
			if (!from || !to) {
				continue;
			}

			const dx = from.x - to.x;
			const dy = from.y - to.y;
			if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) {
				moves.push({ node, dx, dy });
			}
		}

		running.current = moves.map(({ node, dx, dy }) =>
			node.animate(
				[
					{ transform: `translate(${dx}px, ${dy}px)` },
					{ transform: "translate(0, 0)" },
				],
				{ duration, easing: EASE },
			),
		);
	});

	return { capture, register };
}

/** Whether any of `ref` is on screen; once it is, it counts until it leaves. */
export function useInView(ref: RefObject<HTMLElement | null>): boolean {
	const [inView, setInView] = useState(false);

	useEffect(() => {
		const node = ref.current;
		if (!node) {
			return;
		}

		const observer = new IntersectionObserver(
			([entry]) => setInView(entry.isIntersecting),
			{ threshold: 0.35 },
		);
		observer.observe(node);
		return () => observer.disconnect();
	}, [ref]);

	return inView;
}

/**
 * A demo that plays itself until the visitor takes over.
 *
 * It only ticks while on screen, so nobody scrolls down into the middle of a
 * sequence, and it never starts under reduced motion — the visitor can still
 * press play. Any interaction with the demo should call `stop`: a demo that
 * keeps moving the thing you just grabbed is a demo arguing with you.
 */
export function useAutoplay(
	ref: RefObject<HTMLElement | null>,
	interval: number,
	onTick: () => void,
): { playing: boolean; play: () => void; stop: () => void } {
	const reduced = usePrefersReducedMotion();
	const inView = useInView(ref);
	const [choice, setChoice] = useState<"auto" | "playing" | "stopped">("auto");

	const tick = useRef(onTick);
	tick.current = onTick;

	const playing = choice === "playing" || (choice === "auto" && !reduced);

	useEffect(() => {
		if (!playing || !inView) {
			return;
		}

		const id = window.setInterval(() => tick.current(), interval);
		return () => window.clearInterval(id);
	}, [playing, inView, interval]);

	return {
		playing,
		play: useCallback(() => setChoice("playing"), []),
		stop: useCallback(() => setChoice("stopped"), []),
	};
}
