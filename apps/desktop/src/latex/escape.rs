//! Turning user text into LaTeX source.
//!
//! A port of `apps/web/app/lib/latex/escape.ts`. Every string that reaches
//! the template goes through here; a missed escape does not just look wrong,
//! it changes what the rest of the document means or fails the compile.

use crate::api::models::BulletPoint;
use crate::bullets;

/// Escape the ten characters LaTeX treats specially, in a single pass, so a
/// replacement's own braces are never escaped a second time.
pub fn escape(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    for character in value.chars() {
        match character {
            '\\' => out.push_str("\\textbackslash{}"),
            '{' => out.push_str("\\{"),
            '}' => out.push_str("\\}"),
            '$' => out.push_str("\\$"),
            '&' => out.push_str("\\&"),
            '#' => out.push_str("\\#"),
            '_' => out.push_str("\\_"),
            '%' => out.push_str("\\%"),
            '~' => out.push_str("\\textasciitilde{}"),
            '^' => out.push_str("\\textasciicircum{}"),
            other => out.push(other),
        }
    }
    out
}

/// Make a URL safe as the target of `\href` by percent-encoding.
///
/// Jake's template calls `\href` inside other macros' arguments, where
/// hyperref cannot switch catcodes, so backslash escapes would change the
/// address. A `%` that already starts a valid escape is left alone, so a
/// pre-encoded URL survives instead of becoming `%2520`.
pub fn escape_url(url: &str) -> String {
    let chars: Vec<char> = url.chars().collect();
    let mut out = String::with_capacity(url.len());

    for (index, &character) in chars.iter().enumerate() {
        let encoded = match character {
            '\\' => "%5C",
            '{' => "%7B",
            '}' => "%7D",
            '$' => "%24",
            '&' => "%26",
            '#' => "%23",
            '_' => "%5F",
            '^' => "%5E",
            '~' => "%7E",
            '%' => {
                let valid = chars
                    .get(index + 1..index + 3)
                    .is_some_and(|pair| pair.iter().all(char::is_ascii_hexdigit));
                if valid {
                    out.push('%');
                    continue;
                }
                "%25"
            }
            other => {
                out.push(other);
                continue;
            }
        };
        out.push_str(encoded);
    }

    out
}

/// One bullet, its bolded runs wrapped in `\textbf`.
///
/// Each run is escaped on its own: escaping the whole string first would
/// shift every offset and land the bolding in the wrong place.
pub fn bullet(bullet: &BulletPoint) -> String {
    bullets::split(bullet)
        .into_iter()
        .map(|segment| {
            if segment.bold {
                format!("\\textbf{{{}}}", escape(&segment.text))
            } else {
                escape(&segment.text)
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn escapes_in_a_single_pass() {
        assert_eq!(escape("\\"), "\\textbackslash{}");
        assert_eq!(
            escape("{}$&#_%~^"),
            "\\{\\}\\$\\&\\#\\_\\%\\textasciitilde{}\\textasciicircum{}"
        );
    }

    #[test]
    fn leaves_ordinary_and_accented_text_alone() {
        assert_eq!(escape("Café — naïve"), "Café — naïve");
        assert_eq!(escape(""), "");
    }

    #[test]
    fn keeps_a_valid_percent_escape_in_a_url() {
        assert_eq!(escape_url("https://a.b/x%20y"), "https://a.b/x%20y");
        assert_eq!(escape_url("https://a.b/100%"), "https://a.b/100%25");
        assert_eq!(escape_url("https://a.b/%2"), "https://a.b/%252");
        assert_eq!(escape_url("https://a.b/~me_x"), "https://a.b/%7Eme%5Fx");
    }

    #[test]
    fn escapes_inside_and_outside_bold_runs() {
        let point = BulletPoint {
            text: "A&B cut 50%".into(),
            bolded: vec![(0, 2)],
        };
        assert_eq!(bullet(&point), "\\textbf{A\\&B} cut 50\\%");
    }
}
