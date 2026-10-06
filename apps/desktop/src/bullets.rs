//! Bullet points and the runs of them that print bold.
//!
//! Two representations meet here. The API stores **inclusive** ranges of
//! character indices; the editor works in **half-open** ranges, which make
//! the arithmetic of selections and edits far less fiddly. Conversion happens
//! only at the edges — `from_api` on the way in, `to_api` on the way out.
//!
//! Every index is a character index, never a byte offset: the API counts
//! characters, and "Café" has to bold the same letters on both sides.

use crate::api::models::BulletPoint;

/// One run of a bullet's text, plain or bold.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Segment {
    pub text: String,
    pub bold: bool,
}

fn slice(chars: &[char], start: usize, end: usize) -> String {
    chars[start.min(chars.len())..end.min(chars.len())]
        .iter()
        .collect()
}

/// Walk a bullet's text into alternating plain and bold segments.
///
/// The API promises sorted, disjoint ranges; sorting here and skipping a
/// range that starts inside the previous one means a bad payload degrades to
/// lost bolding rather than nested or overlapping output.
pub fn split(bullet: &BulletPoint) -> Vec<Segment> {
    let chars: Vec<char> = bullet.text.chars().collect();
    let mut ranges = bullet.bolded.clone();
    ranges.sort_by_key(|range| range.0);

    let mut segments = Vec::new();
    let mut cursor = 0;

    for (start, end) in ranges {
        if start < cursor || start > end || start >= chars.len() {
            continue;
        }
        if start > cursor {
            segments.push(Segment {
                text: slice(&chars, cursor, start),
                bold: false,
            });
        }
        // `end` is inclusive, so the slice reaches one past it
        segments.push(Segment {
            text: slice(&chars, start, end + 1),
            bold: true,
        });
        cursor = end + 1;
    }

    if cursor < chars.len() {
        segments.push(Segment {
            text: slice(&chars, cursor, chars.len()),
            bold: false,
        });
    }

    segments
}

/// A bullet while it is being edited, with half-open `[start, end)` ranges.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct BulletDraft {
    pub text: String,
    pub bolded: Vec<(usize, usize)>,
}

impl BulletDraft {
    /// The bold and plain runs, for the preview under the field.
    pub fn segments(&self) -> Vec<Segment> {
        let chars: Vec<char> = self.text.chars().collect();
        let mut segments = Vec::new();
        let mut cursor = 0;

        for (start, end) in clamp(&self.bolded, chars.len()) {
            if start > cursor {
                segments.push(Segment {
                    text: slice(&chars, cursor, start),
                    bold: false,
                });
            }
            segments.push(Segment {
                text: slice(&chars, start, end),
                bold: true,
            });
            cursor = end;
        }

        if cursor < chars.len() {
            segments.push(Segment {
                text: slice(&chars, cursor, chars.len()),
                bold: false,
            });
        }

        segments
    }

    /// Replace the text, carrying the bolding along with the words it was on.
    pub fn set_text(&mut self, next: String) {
        self.bolded = remap(&self.text, &next, &self.bolded);
        self.text = next;
    }

    /// Bold the selection, or unbold it if it is already entirely bold.
    pub fn toggle_bold(&mut self, start: usize, end: usize) {
        if end <= start {
            return;
        }
        self.bolded = toggle(&self.bolded, start, end);
    }
}

/// The API's bullets as drafts; an empty list still offers one blank field.
pub fn from_api(bullets: &[BulletPoint]) -> Vec<BulletDraft> {
    let drafts: Vec<BulletDraft> = bullets
        .iter()
        .map(|bullet| BulletDraft {
            text: bullet.text.clone(),
            bolded: bullet
                .bolded
                .iter()
                .map(|&(start, end)| (start, end + 1))
                .collect(),
        })
        .collect();

    if drafts.is_empty() {
        vec![BulletDraft::default()]
    } else {
        drafts
    }
}

/// Drafts back into the API's shape: blank bullets dropped, text trimmed,
/// ranges clamped to what survived the trim and made inclusive again.
pub fn to_api(drafts: &[BulletDraft]) -> Vec<BulletPoint> {
    drafts
        .iter()
        .filter_map(|draft| {
            let leading = draft.text.chars().take_while(|c| c.is_whitespace()).count();
            let text = draft.text.trim().to_string();
            if text.is_empty() {
                return None;
            }

            let length = text.chars().count();
            let shifted: Vec<(usize, usize)> = draft
                .bolded
                .iter()
                .map(|&(start, end)| (start.saturating_sub(leading), end.saturating_sub(leading)))
                .collect();

            Some(BulletPoint {
                bolded: clamp(&shifted, length)
                    .into_iter()
                    .map(|(start, end)| (start, end - 1))
                    .collect(),
                text,
            })
        })
        .collect()
}

/// Sort, merge touching or overlapping ranges, and drop empty ones.
fn normalize(ranges: &[(usize, usize)]) -> Vec<(usize, usize)> {
    let mut sorted: Vec<(usize, usize)> = ranges
        .iter()
        .copied()
        .filter(|(start, end)| end > start)
        .collect();
    sorted.sort_by_key(|range| range.0);

    let mut merged: Vec<(usize, usize)> = Vec::new();
    for (start, end) in sorted {
        match merged.last_mut() {
            Some(previous) if start <= previous.1 => previous.1 = previous.1.max(end),
            _ => merged.push((start, end)),
        }
    }
    merged
}

fn clamp(ranges: &[(usize, usize)], length: usize) -> Vec<(usize, usize)> {
    normalize(
        &ranges
            .iter()
            .map(|&(start, end)| (start.min(length), end.min(length)))
            .collect::<Vec<_>>(),
    )
}

fn toggle(ranges: &[(usize, usize)], from: usize, to: usize) -> Vec<(usize, usize)> {
    let existing = normalize(ranges);
    let already_bold = existing
        .iter()
        .any(|&(start, end)| start <= from && end >= to);

    if !already_bold {
        let mut next = existing;
        next.push((from, to));
        return normalize(&next);
    }

    // unbold: cut the selection out of every range it overlaps
    normalize(
        &existing
            .into_iter()
            .flat_map(|(start, end)| {
                if end <= from || start >= to {
                    vec![(start, end)]
                } else {
                    vec![(start, end.min(from)), (start.max(to), end)]
                }
            })
            .collect::<Vec<_>>(),
    )
}

/// Keep ranges on their words across an edit.
///
/// The unchanged prefix and suffix around the edit locate it; indices before
/// it stay put, indices after it shift by the change in length, and indices
/// inside the replaced span collapse to its start.
fn remap(previous: &str, next: &str, ranges: &[(usize, usize)]) -> Vec<(usize, usize)> {
    if previous == next {
        return ranges.to_vec();
    }

    let before: Vec<char> = previous.chars().collect();
    let after: Vec<char> = next.chars().collect();
    let shorter = before.len().min(after.len());

    let mut prefix = 0;
    while prefix < shorter && before[prefix] == after[prefix] {
        prefix += 1;
    }

    let mut suffix = 0;
    while suffix < shorter - prefix
        && before[before.len() - 1 - suffix] == after[after.len() - 1 - suffix]
    {
        suffix += 1;
    }

    let edit_end = before.len() - suffix;
    let delta = after.len() as isize - before.len() as isize;

    let shift = |index: usize| -> usize {
        if index <= prefix {
            index
        } else if index >= edit_end {
            (index as isize + delta).max(0) as usize
        } else {
            prefix
        }
    };

    clamp(
        &ranges
            .iter()
            .map(|&(start, end)| (shift(start), shift(end)))
            .collect::<Vec<_>>(),
        after.len(),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bullet(text: &str, bolded: &[(usize, usize)]) -> BulletPoint {
        BulletPoint {
            text: text.into(),
            bolded: bolded.to_vec(),
        }
    }

    fn rendered(segments: &[Segment]) -> String {
        segments
            .iter()
            .map(|segment| {
                if segment.bold {
                    format!("[{}]", segment.text)
                } else {
                    segment.text.clone()
                }
            })
            .collect()
    }

    #[test]
    fn split_bolds_an_inclusive_range() {
        assert_eq!(
            rendered(&split(&bullet("Shipped it", &[(0, 6)]))),
            "[Shipped] it"
        );
    }

    #[test]
    fn split_counts_characters_not_bytes() {
        assert_eq!(
            rendered(&split(&bullet("Café crew", &[(5, 8)]))),
            "Café [crew]"
        );
    }

    #[test]
    fn split_skips_overlaps_and_inverted_ranges() {
        let segments = split(&bullet("abcdef", &[(0, 3), (2, 4), (5, 4)]));
        assert_eq!(rendered(&segments), "[abcd]ef");
    }

    #[test]
    fn toggling_twice_leaves_nothing_bold() {
        let mut draft = BulletDraft {
            text: "Cut latency".into(),
            bolded: vec![],
        };
        draft.toggle_bold(0, 3);
        assert_eq!(draft.bolded, vec![(0, 3)]);
        draft.toggle_bold(0, 3);
        assert!(draft.bolded.is_empty());
    }

    #[test]
    fn unbolding_the_middle_splits_a_range() {
        let mut draft = BulletDraft {
            text: "abcdefgh".into(),
            bolded: vec![(0, 8)],
        };
        draft.toggle_bold(3, 5);
        assert_eq!(draft.bolded, vec![(0, 3), (5, 8)]);
    }

    #[test]
    fn typing_before_a_bold_word_moves_the_bold_with_it() {
        let mut draft = BulletDraft {
            text: "Cut latency".into(),
            bolded: vec![(4, 11)],
        };
        draft.set_text("We cut latency".into());
        // "We c" replaced "C": the edit sits at the front
        assert_eq!(rendered(&draft.segments()), "We cut [latency]");
    }

    #[test]
    fn round_trips_through_the_api_shape() {
        let original = vec![bullet("Shipped it", &[(0, 6)])];
        assert_eq!(to_api(&from_api(&original)), original);
    }

    #[test]
    fn to_api_trims_and_shifts_ranges_with_the_text() {
        let drafts = vec![
            BulletDraft {
                text: "  Shipped it  ".into(),
                bolded: vec![(2, 9)],
            },
            BulletDraft {
                text: "   ".into(),
                bolded: vec![],
            },
        ];
        assert_eq!(to_api(&drafts), vec![bullet("Shipped it", &[(0, 6)])]);
    }

    #[test]
    fn an_empty_list_still_offers_one_field() {
        assert_eq!(from_api(&[]), vec![BulletDraft::default()]);
    }
}
