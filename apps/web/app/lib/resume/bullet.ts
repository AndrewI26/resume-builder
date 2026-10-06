/**
 * Splitting a bullet point into its bold and plain runs.
 *
 * Both renderers need this: the LaTeX serializer wraps the bold runs in
 * `\textbf`, the preview wraps them in `<strong>`. Doing the offset arithmetic
 * once means the two cannot disagree about where the bolding lands.
 */

import type { BulletPoint } from "./types";

export interface Segment {
	text: string;
	bold: boolean;
	/** Where this run starts in the bullet's text. Stable across re-renders. */
	start: number;
}

/**
 * Walk a bullet's text into alternating plain and bold segments.
 *
 * `bolded` ranges are inclusive on both ends. The API guarantees they arrive
 * sorted and disjoint; the sort and the `start < cursor` skip here mean a bad
 * payload degrades to dropped bolding rather than overlapping output.
 */
export function splitBullet(bullet: BulletPoint): Segment[] {
	const ranges = [...bullet.bolded].sort((a, b) => a[0] - b[0]);

	const segments: Segment[] = [];
	let cursor = 0;

	for (const [start, end] of ranges) {
		// a range that did not arrive as a usable pair is dropped rather than
		// trusted; see the note on BulletPoint.bolded
		if (start === undefined || end === undefined) continue;
		if (start < cursor || start > end || start < 0) continue;

		if (start > cursor) {
			segments.push({
				text: bullet.text.slice(cursor, start),
				bold: false,
				start: cursor,
			});
		}
		// `end` is inclusive, so the slice has to reach one past it
		segments.push({
			text: bullet.text.slice(start, end + 1),
			bold: true,
			start,
		});
		cursor = end + 1;
	}

	if (cursor < bullet.text.length) {
		segments.push({
			text: bullet.text.slice(cursor),
			bold: false,
			start: cursor,
		});
	}

	return segments;
}
